# app/handlers/topup.py
import asyncio
import base64
import os
import ast
import tempfile
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile

from app.i18n import t
from app.keyboards.topup import kb_topup_methods, kb_topup_cancel, kb_topup_pending_actions
from app.config import settings
from app.utils import format_amount

router = Router()
log = logging.getLogger("topup")


def _should_cancel_flow(state: str | None) -> bool:
    return state in ("buy_wait_qty", "buy_wait_confirm", "topup_choose", "topup_wait_amount", "ticket_wait_text")


def _parse_http_error(e: Exception):
    """
    HttpClient của bạn ném RuntimeError dạng: "http_error:409:{...}"
    """
    msg = str(e)
    if not msg.startswith("http_error:"):
        return None
    parts = msg.split(":", 2)
    if len(parts) < 3:
        return None
    status = int(parts[1])
    raw = parts[2]
    try:
        data = ast.literal_eval(raw)
    except Exception:
        data = {"raw": raw}
    return status, data


@router.message(Command("topup"))
async def cmd_topup(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)
    order_api = data["order_api"]

    # ✅ Check banned status trước khi cho phép topup
    try:
        telegram_user = message.from_user.username  # Có thể là None
        me_data = await order_api.me(message.from_user.id, telegram_user)
        if me_data.get("is_banned", False):
            await message.answer(t(s.lang, "user_banned"))
            return
    except Exception:
        # Nếu không check được thì cho phép tiếp tục (fallback)
        pass

    if _should_cancel_flow(getattr(s, "state", None)):
        storage.reset_flow(message.from_user.id)
        from app.services.telegram_utils import safe_answer
        await safe_answer(message, t(s.lang, "cancel_flow"))
        s = storage.get(message.from_user.id)

    s.state = "topup_choose"
    await message.answer(t(s.lang, "topup_choose_method"), reply_markup=kb_topup_methods())


@router.callback_query(lambda c: c.data == "topup:cancel")
async def cb_topup_cancel(cb: CallbackQuery, **data):
    storage = data["storage"]
    storage.reset_flow(cb.from_user.id)
    s = storage.get(cb.from_user.id)
    await cb.answer("OK")
    await cb.message.answer(t(s.lang, "start"))


@router.callback_query(lambda c: c.data and c.data.startswith("topup:net:"))
async def cb_topup_choose_net(cb: CallbackQuery, **data):
    storage = data["storage"]
    s = storage.get(cb.from_user.id)

    parts = cb.data.split(":")
    network = parts[2]
    coin = ":".join(parts[3:])
    s.topup_network = network
    s.topup_coin = coin
    s.state = "topup_wait_amount"

    # Answer callback ngay để giảm latency
    await cb.answer()
    await cb.message.answer(t(s.lang, "topup_ask_amount"), reply_markup=kb_topup_cancel())


@router.callback_query(lambda c: c.data and c.data.startswith("topup:cancel_pending:"))
async def cb_cancel_pending(cb: CallbackQuery, **data):
    payment_api = data["payment_api"]
    storage = data["storage"]
    s = storage.get(cb.from_user.id)

    topup_id = cb.data.split(":", 2)[-1]
    try:
        # Gọi API cancel để đổi status thành CANCELED
        result = await payment_api.cancel_topup(cb.from_user.id, topup_id)
        
        # Kiểm tra response để đảm bảo đã cancel thành công
        if result and result.get("ok") and result.get("status") in ("CANCELED", "FAILED"):
            storage.reset_flow(cb.from_user.id)
            await cb.answer(t(s.lang, "cancelled"))
            await cb.message.answer(t(s.lang, "topup_cancelled"))
        else:
            # Nếu status không phải CANCELED, có thể đã được cancel trước đó hoặc có lỗi
            await cb.answer(t(s.lang, "generic_error"), show_alert=True)
            
    except Exception as e:
        log.exception("cancel_topup failed: %s", e)
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        await cb.message.answer(t(s.lang, "generic_error"))


# ✅ CHỈ BẮT TIN NHẮN “CÓ SỐ”
@router.message(lambda m: m.text and any(ch.isdigit() for ch in m.text))
async def catch_topup_amount(message: Message, **data):
    storage = data["storage"]
    payment_api = data["payment_api"]
    bot = data["bot"]
    s = storage.get(message.from_user.id)

    if s.state != "topup_wait_amount":
        return

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError()
    except Exception:
        await message.answer(t(s.lang, "generic_error"))
        return

    try:
        telegram_user = message.from_user.username  # Có thể là None
        invoice = await payment_api.create_topup(
            telegram_id=message.from_user.id,
            network=s.topup_network,
            coin=s.topup_coin,
            amount=amount,
            telegram_user=telegram_user,
        )

        topup_id = str(invoice.get("topup_id"))
        address = invoice.get("address", "")
        qr_b64 = invoice.get("qr_base64", "")
        if isinstance(qr_b64, str) and qr_b64.startswith("data:image"):
            qr_b64 = qr_b64.split("base64,", 1)[-1].strip()

        tmp_path = None
        if qr_b64:
            qr_bytes = base64.b64decode(qr_b64)
            fd, tmp_path = tempfile.mkstemp(prefix="qr_", suffix=".png")
            os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(qr_bytes)

            formatted_amount = format_amount(invoice.get("amount", amount))
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=FSInputFile(tmp_path),
                caption=t(
                    s.lang,
                    "topup_invoice",
                    network=s.topup_network,
                    coin=s.topup_coin,
                    amount=formatted_amount,
                    address=address
                ),
                reply_markup=kb_topup_pending_actions(topup_id)  # ✅ có nút cancel pending
            )
        else:
            formatted_amount = format_amount(invoice.get("amount", amount))
            await message.answer(
                t(
                    s.lang,
                    "topup_invoice",
                    network=s.topup_network,
                    coin=s.topup_coin,
                    amount=formatted_amount,
                    address=address
                ),
                reply_markup=kb_topup_pending_actions(topup_id)  # ✅ có nút cancel pending
            )

        # ✅ Gửi thông báo về phí sàn
        await message.answer(
            t(
                s.lang,
                "topup_exchange_fee_warning",
                amount=formatted_amount
            )
        )

        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        s.state = "idle"
        asyncio.create_task(
            poll_topup_status(bot, message.chat.id, message.from_user.id, payment_api, topup_id, s.lang)
        )

    except Exception as e:
        parsed = _parse_http_error(e)
        msg = str(e)
        if "USER_BANNED" in msg or (parsed and parsed[0] == 403):
            await message.answer(t(s.lang, "user_banned"))
            storage.reset_flow(message.from_user.id)
            return
        if parsed and parsed[0] == 409:
            payload = parsed[1]
            
            # Backend trả về dict trực tiếp: {code: 'PENDING_EXISTS', topup_id: ..., expire_time: ...}
            # Hoặc có thể có key "detail" chứa dict
            detail = payload if isinstance(payload, dict) else (payload.get("detail") if isinstance(payload, dict) else None)

            # Kiểm tra nếu là PENDING_EXISTS
            if isinstance(detail, dict) and detail.get("code") == "PENDING_EXISTS":
                pending_id = str(detail.get("topup_id") or "")
                exp = detail.get("expire_time", "")
                
                # Lấy thông tin topup pending để hiển thị invoice
                try:
                    bot = data.get("bot")
                    if bot and pending_id:
                        # Lấy thông tin topup từ API để hiển thị đầy đủ
                        topup_data = await payment_api.get_topup(pending_id)
                        if topup_data:
                            # Hiển thị invoice tương tự như khi tạo mới
                            address = topup_data.get("to_address") or topup_data.get("address", "")
                            qr_b64 = topup_data.get("qr_code_base64") or topup_data.get("qr_base64", "")
                            amount = topup_data.get("amount") or topup_data.get("actual_amount", amount)
                            network = topup_data.get("network", s.topup_network)
                            coin = topup_data.get("coin") or topup_data.get("currency", s.topup_coin)
                            
                            tmp_path = None
                            if qr_b64:
                                if isinstance(qr_b64, str) and qr_b64.startswith("data:image"):
                                    qr_b64 = qr_b64.split("base64,", 1)[-1].strip()
                                try:
                                    qr_bytes = base64.b64decode(qr_b64)
                                    fd, tmp_path = tempfile.mkstemp(prefix="qr_", suffix=".png")
                                    os.close(fd)
                                    with open(tmp_path, "wb") as f:
                                        f.write(qr_bytes)

                                    formatted_amount_pending = format_amount(amount)
                                    await bot.send_photo(
                                        chat_id=message.chat.id,
                                        photo=FSInputFile(tmp_path),
                                        caption=t(
                                            s.lang,
                                            "topup_invoice",
                                            network=network,
                                            coin=coin,
                                            amount=formatted_amount_pending,
                                            address=address
                                        ),
                                        reply_markup=kb_topup_pending_actions(pending_id)
                                    )
                                    if tmp_path and os.path.exists(tmp_path):
                                        try:
                                            os.remove(tmp_path)
                                        except Exception:
                                            pass
                                except Exception as qr_err:
                                    log.warning("Failed to decode QR: %s", qr_err)
                            else:
                                formatted_amount_pending = format_amount(amount)
                                await message.answer(
                                    t(
                                        s.lang,
                                        "topup_invoice",
                                        network=network,
                                        coin=coin,
                                        amount=formatted_amount_pending,
                                        address=address
                                    ),
                                    reply_markup=kb_topup_pending_actions(pending_id)
                                )
                            
                            # Thông báo về topup pending
                            await message.answer(
                                t(s.lang, "topup_pending_exists", topup_id=pending_id, expire_time=exp),
                                reply_markup=kb_topup_pending_actions(pending_id)
                            )
                            return
                except Exception as get_err:
                    log.warning("Failed to get topup details: %s", get_err)
                
                # Fallback: chỉ hiển thị thông báo đơn giản
                await message.answer(
                    t(s.lang, "topup_pending_exists", topup_id=pending_id, expire_time=exp),
                    reply_markup=kb_topup_pending_actions(pending_id)
                )
                return

        log.exception("create_topup failed: %s", e)
        await message.answer(t(s.lang, "generic_error"))
        storage.reset_flow(message.from_user.id)


async def poll_topup_status(bot, chat_id: int, telegram_id: int, payment_api, topup_id: str, lang: str):
    sent_pending = False
    for _ in range(settings.TOPUP_POLL_MAX_TIMES):
        try:
            data = await payment_api.get_topup(topup_id)
            status = str(data.get("status", "PENDING")).upper()

            if status in ("SUCCESS", "PAID", "CONFIRMED"):
                await bot.send_message(chat_id, t(lang, "topup_success", topup_id=topup_id))
                return

            if status in ("FAILED", "EXPIRED", "CANCELED"):
                await bot.send_message(chat_id, t(lang, "topup_failed", topup_id=topup_id))
                return

            if not sent_pending:
                await bot.send_message(chat_id, t(lang, "topup_pending", topup_id=topup_id))
                sent_pending = True

        except Exception:
            pass

        await asyncio.sleep(settings.TOPUP_POLL_INTERVAL_SEC)

    await bot.send_message(chat_id, t(lang, "topup_failed", topup_id=topup_id))
