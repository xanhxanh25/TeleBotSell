# app/handlers/topup.py
import asyncio
import base64
import os
import ast
import json
import tempfile
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
try:
    from aiogram.exceptions import SkipHandler
except ImportError:
    try:
        from aiogram.dispatcher.handler import SkipHandler
    except ImportError:
        from aiogram.dispatcher.event.bases import SkipHandler

from app.i18n import t
from app.keyboards.topup import kb_topup_methods, kb_topup_cancel, kb_topup_pending_actions
from app.config import settings
from app.services.flow_runtime import action_guard, reset_user_flow, task_registry
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
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}
    return status, data


def _extract_error_detail(payload):
    if isinstance(payload, dict):
        detail = payload.get("detail")
        return detail if isinstance(detail, dict) else payload
    return None


async def _send_invoice(bot, chat_id: int, message, invoice: dict, s, topup_id: str):
    """
    Gửi invoice cho user.
    - Nếu là Binance Pay → hiển thị BinanceId + Note (không có QR).
    - Nếu là on-chain → hiển thị địa chỉ ví + QR code.
    """
    from app.i18n import t

    formatted_amount = format_amount(invoice.get("amount") or invoice.get("actual_amount", ""))
    network  = invoice.get("network") or s.topup_network
    coin     = invoice.get("currency") or s.topup_coin
    address  = invoice.get("address", "")

    binance_id    = invoice.get("binance_id")
    note_to_payee = invoice.get("note_to_payee")

    # ── Binance Pay ───────────────────────────────────────────────────────
    if binance_id and note_to_payee:
        caption_text = t(s.lang, "topup_binance_pay_invoice",
                         binance_id=binance_id,
                         note=note_to_payee,
                         amount=formatted_amount)

        # Gửi ảnh QR Binance cố định (qrbinance.png)
        import os as _os, pathlib as _pathlib
        _qr_path = _pathlib.Path(__file__).resolve().parents[2] / "qrbinance.png"
        if _qr_path.is_file():
            await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(str(_qr_path)),
                caption=caption_text,
                reply_markup=kb_topup_pending_actions(topup_id),
            )
        else:
            await message.answer(
                caption_text,
                reply_markup=kb_topup_pending_actions(topup_id),
            )
        return

    # ── On-chain: QR + địa chỉ ───────────────────────────────────────────
    qr_b64 = invoice.get("qr_base64", "")
    if isinstance(qr_b64, str) and qr_b64.startswith("data:image"):
        qr_b64 = qr_b64.split("base64,", 1)[-1].strip()

    tmp_path = None
    try:
        if qr_b64:
            import base64 as _b64, tempfile as _tmp, os as _os
            qr_bytes = _b64.b64decode(qr_b64)
            fd, tmp_path = _tmp.mkstemp(prefix="qr_", suffix=".png")
            _os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(qr_bytes)
            await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(tmp_path),
                caption=t(s.lang, "topup_invoice",
                          network=network, coin=coin,
                          amount=formatted_amount, address=address),
                reply_markup=kb_topup_pending_actions(topup_id),
            )
        else:
            await message.answer(
                t(s.lang, "topup_invoice",
                  network=network, coin=coin,
                  amount=formatted_amount, address=address),
                reply_markup=kb_topup_pending_actions(topup_id),
            )
    finally:
        if tmp_path:
            import os as _os
            try:
                _os.remove(tmp_path)
            except Exception:
                pass


@router.message(Command("topup"))
async def cmd_topup(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)
    order_api = data["order_api"]

    # ✅ Check banned status trước khi cho phép topup
    try:
        telegram_user = message.from_user.username  # Có thể là None
        me_data = await asyncio.wait_for(
            order_api.me(message.from_user.id, telegram_user),
            timeout=2.5,
        )
        if me_data.get("is_banned", False):
            await message.answer(t(s.lang, "user_banned"))
            return
    except Exception:
        # Nếu check chậm/lỗi thì cho phép tiếp tục; backend vẫn chặn user banned khi tạo topup.
        pass

    if _should_cancel_flow(getattr(s, "state", None)):
        await reset_user_flow(storage, message.from_user.id, reason="topup_command_interrupt")
        from app.services.telegram_utils import safe_answer
        await safe_answer(message, t(s.lang, "cancel_flow"))
        s = storage.get(message.from_user.id)

    s.state = "topup_choose"
    await message.answer(t(s.lang, "topup_choose_method"), reply_markup=kb_topup_methods())


@router.callback_query(lambda c: c.data == "topup:cancel")
async def cb_topup_cancel(cb: CallbackQuery, **data):
    storage = data["storage"]
    await reset_user_flow(storage, cb.from_user.id, reason="topup_cancel")
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
    async with action_guard.hold(cb.from_user.id) as locked:
        if not locked:
            await cb.answer("Processing...", show_alert=False)
            return
        try:
        # Gọi API cancel để đổi status thành CANCELED
            result = await payment_api.cancel_topup(cb.from_user.id, topup_id)
        
        # Kiểm tra response để đảm bảo đã cancel thành công
            if result and result.get("ok") and result.get("status") in ("CANCELED", "FAILED"):
                await reset_user_flow(storage, cb.from_user.id, reason="topup_cancel_pending")
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

    # Nếu user đang ở bước chọn mạng mà nhập số luôn, nhắc chọn network trước
    # thay vì im lặng để tránh cảm giác bot "không nhận".
    if s.state == "topup_choose":
        await message.answer(t(s.lang, "topup_choose_method"), reply_markup=kb_topup_methods())
        return

    if s.state != "topup_wait_amount":
        raise SkipHandler()

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError()
    except Exception:
        await message.answer(t(s.lang, "generic_error"))
        return

    async with action_guard.hold(message.from_user.id) as locked:
        if not locked:
            await message.answer("Processing previous request, please wait...")
            return
        try:
            telegram_user = message.from_user.username
            invoice = await payment_api.create_topup(
                telegram_id=message.from_user.id,
                network=s.topup_network,
                coin=s.topup_coin,
                amount=amount,
                telegram_user=telegram_user,
            )

            topup_id = str(invoice.get("topup_id"))
            await _send_invoice(bot, message.chat.id, message, invoice, s, topup_id)

            # Cảnh báo phí chỉ cần cho on-chain, không cần cho Binance Pay
            if not invoice.get("binance_id"):
                formatted_amount = format_amount(invoice.get("amount", amount))
                await message.answer(
                    t(s.lang, "topup_exchange_fee_warning", amount=formatted_amount)
                )

            s.state = "idle"
            poll_task = asyncio.create_task(
                poll_topup_status(bot, message.chat.id, message.from_user.id, payment_api, topup_id, s.lang)
            )
            await task_registry.register_singleton(message.from_user.id, "topup_poll", poll_task)

        except Exception as e:
            parsed = _parse_http_error(e)
            msg = str(e)
            if "USER_BANNED" in msg or (parsed and parsed[0] == 403):
                await message.answer(t(s.lang, "user_banned"))
                await reset_user_flow(storage, message.from_user.id, reason="topup_user_banned")
                return
            if parsed and parsed[0] == 409:
                payload = parsed[1]
                detail = _extract_error_detail(payload)

            # Kiểm tra nếu là PENDING_EXISTS
                if isinstance(detail, dict) and detail.get("code") == "PENDING_EXISTS":
                    pending_id = str(detail.get("topup_id") or "")
                    exp = detail.get("expire_time", "")
                
                # Lấy thông tin topup pending để hiển thị invoice
                    try:
                        bot = data.get("bot")
                        if bot and pending_id:
                            topup_data = await payment_api.get_topup(pending_id)
                            if topup_data:
                                await _send_invoice(bot, message.chat.id, message,
                                                    topup_data, s, pending_id)
                                await message.answer(
                                    t(s.lang, "topup_pending_exists",
                                      topup_id=pending_id, expire_time=exp),
                                    reply_markup=kb_topup_pending_actions(pending_id),
                                )
                                return
                    except Exception as get_err:
                        log.warning("Failed to get topup details: %s", get_err)
                
                # Fallback: chỉ hiển thị thông báo đơn giản
                    if pending_id:
                        await message.answer(
                            t(s.lang, "topup_pending_exists", topup_id=pending_id, expire_time=exp),
                            reply_markup=kb_topup_pending_actions(pending_id)
                        )
                    else:
                        await message.answer(t(s.lang, "server_error"))
                    return

            log.exception("create_topup failed: %s", e)
            await message.answer(t(s.lang, "generic_error"))
            await reset_user_flow(storage, message.from_user.id, reason="topup_create_error")


async def poll_topup_status(bot, chat_id: int, telegram_id: int, payment_api, topup_id: str, lang: str):
    sent_pending = False
    consecutive_errors = 0
    for _ in range(settings.TOPUP_POLL_MAX_TIMES):
        try:
            data = await payment_api.get_topup(topup_id)
            consecutive_errors = 0
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
            consecutive_errors += 1
            if consecutive_errors >= 3:
                await bot.send_message(chat_id, t(lang, "server_error"))
                return

        await asyncio.sleep(settings.TOPUP_POLL_INTERVAL_SEC)

    await bot.send_message(chat_id, t(lang, "topup_pending", topup_id=topup_id))
