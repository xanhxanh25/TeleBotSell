import logging
import tempfile
import os
import asyncio
import html
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
try:
    # một số bản aiogram v3
    from aiogram.exceptions import SkipHandler
except ImportError:
    try:
        # aiogram v2.x
        from aiogram.dispatcher.handler import SkipHandler
    except ImportError:
        # một số bản aiogram v3 khác
        from aiogram.dispatcher.event.bases import SkipHandler
from app.i18n import t, t_coupon_api_code
from app.keyboards.products import kb_products, kb_product_actions, kb_confirm_buy
from app.services.api_errors import extract_error_code_from_http_runtime
from app.services.telegram_utils import safe_answer, safe_edit_text, safe_answer_callback, safe_edit_reply_markup
from app.utils import format_amount

router = Router()
log = logging.getLogger("menu")


def _should_cancel_flow(state: str | None) -> bool:
    # các state đang "dở dang"
    return state in (
    "buy_wait_qty",
    "buy_wait_coupon",  # ✅ thêm state cho coupon
    "buy_wait_confirm",
    "buy_processing",   # ✅ thêm
    "topup_choose",
    "topup_wait_amount",
    "ticket_wait_text",
    "error_select_order",
    "error_wait_reason",
    "error_wait_confirm",
)


@router.message(Command("menu"))
async def cmd_menu(message: Message, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(message.from_user.id)

    # ✅ Check banned status trước khi cho phép xem menu
    try:
        telegram_user = message.from_user.username  # Có thể là None
        me_data = await asyncio.wait_for(
            order_api.me(message.from_user.id, telegram_user),
            timeout=2.5,
        )
        if me_data.get("is_banned", False):
            await safe_answer(message, t(s.lang, "user_banned"))
            return
    except Exception:
        # Nếu check chậm/lỗi thì không block UX; các bước mua vẫn được backend kiểm tra lại.
        pass

    # ✅ Nếu đang ở flow khác => auto-cancel + thông báo
    if _should_cancel_flow(getattr(s, "state", None)):
        storage.reset_flow(message.from_user.id)
        await safe_answer(message, t(s.lang, "cancel_flow"))
        s = storage.get(message.from_user.id)

    products = await order_api.list_products(lang=s.lang)
    await safe_answer(message, t(s.lang, "menu_title"), reply_markup=kb_products(products))


@router.callback_query(lambda c: c.data == "menu:back")
async def cb_menu_back(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)

    # Answer callback ngay để giảm latency
    await safe_answer_callback(cb)
    products = await order_api.list_products(lang=s.lang)
    await safe_edit_text(cb.message, t(s.lang, "menu_title"), reply_markup=kb_products(products))


@router.callback_query(lambda c: c.data and c.data.startswith("p:open:"))
async def cb_product_open(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)

    pid = cb.data.split(":")[2]
    p = await order_api.get_product(pid, lang=s.lang)

    qty_discount_info = ""
    tiers = p.get("qty_discount_tiers") or []
    if tiers:
        try:
            lines = []
            for row in sorted(tiers, key=lambda x: int(x.get("min_qty") or 0)):
                mq = row.get("min_qty")
                pct = str(row.get("percent", "")).rstrip("0").rstrip(".")
                lines.append(f"{mq}+ → {pct}%")
            qty_discount_info = t(s.lang, "qty_discount_tiers_info", lines=", ".join(lines))
        except Exception:
            qty_discount_info = ""
    else:
        qty_discount_min = p.get("qty_discount_min")
        qty_discount_percent = p.get("qty_discount_percent")
        if qty_discount_min and qty_discount_percent:
            try:
                percent = float(qty_discount_percent)
                qty_discount_info = t(
                    s.lang,
                    "qty_discount_info",
                    min_qty=qty_discount_min,
                    percent=int(percent),
                )
            except Exception:
                pass

    product_price = format_amount(p.get("price", ""))
    safe_name = html.escape(str(p.get("name", "")), quote=False)
    safe_desc = html.escape(str(p.get("description", "")), quote=False)
    await safe_edit_text(
        cb.message,
        t(
            s.lang,
            "product_detail",
            name=safe_name,
            desc=safe_desc,
            price=product_price,
            stock=p.get("stock", ""),
            qty_discount_info=qty_discount_info,
        ),
        reply_markup=kb_product_actions(pid),
    )
    await safe_answer_callback(cb)


@router.callback_query(lambda c: c.data and c.data.startswith("p:buy:"))
async def cb_product_buy(cb: CallbackQuery, **data):
    storage = data["storage"]
    s = storage.get(cb.from_user.id)
    pid = cb.data.split(":")[2]

    s.state = "buy_wait_qty"
    s.product_id = pid
    s.qty = None
    s.coupon = None

    # Answer callback ngay để giảm latency
    await safe_answer_callback(cb)
    await safe_answer(cb.message, t(s.lang, "ask_qty"))


# ✅ CHỈ BẮT TIN NHẮN LÀ SỐ (tránh chặn /me /start /help)
@router.message(lambda m: m.text and m.text.strip().isdigit())
async def catch_qty_and_flow(message: Message, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(message.from_user.id)

    # Không đúng flow thì bỏ qua
    if not s or s.state != "buy_wait_qty":
        raise SkipHandler()

    try:
        qty = int(message.text.strip())
        if qty <= 0:
            raise ValueError()
        # Cho phép mua không giới hạn số lượng (bỏ giới hạn 999)
    except (ValueError, OverflowError):
        await message.answer(t(s.lang, "generic_error"))
        return

    s.qty = qty

    try:
        # Chạy song song quote và me để giảm thời gian
        telegram_user = message.from_user.username  # Có thể là None
        quote_task = order_api.quote(message.from_user.id, s.product_id, qty, s.coupon, telegram_user)
        me_task = order_api.me(message.from_user.id, telegram_user)
        quote, me = await asyncio.wait_for(
            asyncio.gather(quote_task, me_task, return_exceptions=True),
            timeout=20,
        )
        
        # Xử lý lỗi quote
        if isinstance(quote, Exception):
            msg = str(quote)
            log.error("Quote error: %s", msg)
            
            # Kiểm tra các loại lỗi
            if "OUT_OF_STOCK" in msg:
                # Lấy số lượng còn lại từ error message nếu có
                stock_info = ""
                try:
                    # Có thể parse thêm thông tin từ error
                    if ":" in msg:
                        parts = msg.split(":")
                        if len(parts) > 1:
                            stock_info = f"\n📦 Số lượng còn lại: {parts[-1].strip()}" if parts[-1].strip().isdigit() else ""
                except:
                    pass
                await safe_answer(
                    message,
                    t(s.lang, "out_of_stock_detail", qty=qty, stock_info=stock_info)
                )
            elif "PRODUCT_NOT_FOUND" in msg:
                await safe_answer(message, t(s.lang, "product_not_found"))
            elif "USER_BANNED" in msg or "http_error:403" in msg or "403" in msg:
                await safe_answer(message, t(s.lang, "user_banned"))
            elif "http_error:400" in msg or "400" in msg:
                # Lỗi 400 có thể là OUT_OF_STOCK hoặc validation error
                if "OUT_OF_STOCK" not in msg:
                    await safe_answer(message, t(s.lang, "invalid_data"))
                else:
                    await safe_answer(
                        message,
                        t(s.lang, "out_of_stock_detail", qty=qty, stock_info="")
                    )
            elif "server_error" in msg.lower() or "connection_error" in msg.lower() or "500" in msg:
                log.error("Backend error in quote: %s", msg)
                await safe_answer(message, t(s.lang, "server_error"))
            else:
                log.error("Unknown quote error: %s", msg)
                await safe_answer(message, t(s.lang, "generic_error"))
            storage.reset_flow(message.from_user.id)
            return
        
        # Xử lý lỗi me (fallback)
        if isinstance(me, Exception):
            log.warning("Error getting user balance: %s", me)
            me = {"balance": 0}
        
        # Validate quote response
        if not isinstance(quote, dict):
            log.error("Invalid quote response: %s", type(quote))
            await safe_answer(message, t(s.lang, "generic_error"))
            storage.reset_flow(message.from_user.id)
            return

    except asyncio.TimeoutError:
        log.error("Timeout quote/me for user=%s product=%s qty=%s", message.from_user.id, s.product_id, qty)
        await safe_answer(message, t(s.lang, "server_error"))
        storage.reset_flow(message.from_user.id)
        return
    except Exception as e:
        log.exception("Error in quote/me: %s", e)
        await safe_answer(message, t(s.lang, "generic_error"))
        storage.reset_flow(message.from_user.id)
        return

    # 3) Hiển thị quote để confirm (không kiểm tra balance ở đây)
    coupon_display = quote.get("coupon") or t(s.lang, "none_coupon")
    discount_val = float(quote.get('discount', 0)) if quote.get("discount") else 0.0
    discount_display = format_amount(discount_val)
    
    await safe_answer(
        message,
        t(
            s.lang,
            "quote",
            subtotal=format_amount(float(quote.get('subtotal', 0))),
            discount=discount_display,
            coupon=coupon_display,
            total=format_amount(float(quote.get('total', 0))),
        ),
        reply_markup=kb_confirm_buy(has_coupon=bool(s.coupon)),
    )
    if quote.get("coupon_usage_hint") and quote.get("coupon"):
        await safe_answer(message, html.escape(str(quote.get("coupon_usage_hint")), quote=False))
    s.state = "buy_wait_confirm"


# ✅ APPLY COUPON
@router.callback_query(lambda c: c.data == "buy:apply_coupon")
async def cb_apply_coupon(cb: CallbackQuery, **data):
    storage = data["storage"]
    s = storage.get(cb.from_user.id)
    
    if s.state != "buy_wait_confirm" or not s.product_id or not s.qty:
        await safe_answer_callback(cb, "Invalid state", show_alert=False)
        return
    
    s.state = "buy_wait_coupon"
    # Answer callback ngay để giảm latency
    await safe_answer_callback(cb)
    await safe_answer(cb.message, t(s.lang, "ask_coupon"))


# ✅ HANDLE COUPON INPUT
# Chấp nhận:
#   - Text thường (mã coupon)
#   - Lệnh /skip để bỏ qua coupon
@router.message(
    lambda m: m.text
    and (not m.text.startswith("/") or m.text.strip().lower() in ["/skip"])
)
async def catch_coupon_input(message: Message, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(message.from_user.id)
    
    # Chỉ xử lý khi đang ở state buy_wait_coupon
    if not s or s.state != "buy_wait_coupon":
        raise SkipHandler()
    
    # Nếu là /skip hoặc bỏ qua thì skip coupon
    text_lower = message.text.strip().lower()
    if text_lower in ["/skip", "skip", "bỏ qua", "bo qua", "không", "khong", "no"]:
        s.state = "buy_wait_confirm"
        # Reload quote không có coupon
        try:
            telegram_user = message.from_user.username  # Có thể là None
            quote_task = order_api.quote(message.from_user.id, s.product_id, s.qty, None, telegram_user)
            me_task = order_api.me(message.from_user.id, telegram_user)
            quote, me = await asyncio.wait_for(
                asyncio.gather(quote_task, me_task, return_exceptions=True),
                timeout=20,
            )
            
            if isinstance(quote, Exception) or not isinstance(quote, dict):
                await message.answer(t(s.lang, "generic_error"))
                storage.reset_flow(message.from_user.id)
                return
            
            s.coupon = None
            coupon_display = t(s.lang, "none_coupon")
            discount_val = float(quote.get('discount', 0)) if quote.get("discount") else 0.0
            discount_display = format_amount(discount_val)
            
            await message.answer(
                t(
                    s.lang,
                    "quote",
                    subtotal=format_amount(float(quote.get('subtotal', 0))),
                    discount=discount_display,
                    coupon=coupon_display,
                    total=format_amount(float(quote.get('total', 0))),
                ),
                reply_markup=kb_confirm_buy(has_coupon=False),
            )
            s.state = "buy_wait_confirm"
        except Exception as e:
            log.error("Error reloading quote: %s", e)
            await message.answer(t(s.lang, "generic_error"))
        return
    
    coupon_code = message.text.strip().upper()
    
    # Validate và apply coupon
    try:
        telegram_user = message.from_user.username  # Có thể là None
        quote_task = order_api.quote(message.from_user.id, s.product_id, s.qty, coupon_code, telegram_user)
        me_task = order_api.me(message.from_user.id, telegram_user)
        quote, me = await asyncio.wait_for(
            asyncio.gather(quote_task, me_task, return_exceptions=True),
            timeout=20,
        )
        
        if isinstance(quote, Exception):
            msg = str(quote)
            if "USER_BANNED" in msg or "http_error:403" in msg or "403" in msg:
                await message.answer(t(s.lang, "user_banned"))
                storage.reset_flow(message.from_user.id)
                return
            c_err = extract_error_code_from_http_runtime(msg)
            await message.answer(t_coupon_api_code(s.lang, c_err))
            return
        
        if not isinstance(quote, dict):
            await message.answer(t(s.lang, "generic_error"))
            return
        
        # Xử lý lỗi me (fallback)
        if isinstance(me, Exception):
            log.warning("Error getting user balance when applying coupon: %s", me)
            me = {"balance": 0}

        err = quote.get("coupon_error")
        if err:
            await message.answer(t_coupon_api_code(s.lang, err))
            return

        applied_coupon = quote.get("coupon")
        if applied_coupon and applied_coupon.upper() == coupon_code.upper():
            s.coupon = coupon_code
            await message.answer(
                t(s.lang, "coupon_applied", coupon=html.escape(coupon_code, quote=False))
            )
        else:
            await message.answer(t_coupon_api_code(s.lang, "COUPON_INVALID"))
            return
        
        # Reload quote với coupon (không kiểm tra balance ở đây, sẽ kiểm tra ở confirm)
        coupon_display = html.escape(str(applied_coupon or "None"), quote=False)
        discount_val = float(quote.get('discount', 0)) if quote.get("discount") else 0.0
        discount_display = format_amount(discount_val)
        
        await message.answer(
            t(
                s.lang,
                "quote",
                subtotal=format_amount(float(quote.get('subtotal', 0))),
                discount=discount_display,
                coupon=coupon_display,
                total=format_amount(float(quote.get('total', 0))),
            ),
            reply_markup=kb_confirm_buy(has_coupon=True),
        )
        if quote.get("coupon_usage_hint"):
            await message.answer(html.escape(str(quote.get("coupon_usage_hint")), quote=False))
        s.state = "buy_wait_confirm"
        
    except Exception as e:
        log.error("Error applying coupon: %s", e)
        await message.answer(t(s.lang, "generic_error"))


# ✅ CONFIRM BUY
@router.callback_query(lambda c: c.data == "buy:confirm")
async def cb_buy_confirm(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)

    # Nếu bấm confirm khi không đúng state
    if s.state != "buy_wait_confirm" or not s.product_id or not s.qty:
        await cb.answer("Invalid state", show_alert=False)
        return

    # ✅ Kiểm tra số dư trước khi checkout
    try:
        telegram_user = cb.from_user.username  # Có thể là None
        # Lấy quote mới nhất với coupon (nếu có) và balance
        quote_task = order_api.quote(cb.from_user.id, s.product_id, s.qty, s.coupon, telegram_user)
        me_task = order_api.me(cb.from_user.id, telegram_user)
        quote, me = await asyncio.gather(quote_task, me_task, return_exceptions=True)
        
        # Xử lý lỗi
        if isinstance(quote, Exception):
            log.error("Error getting quote for balance check: %s", quote)
            await cb.answer(t(s.lang, "generic_error"), show_alert=True)
            return
        
        if isinstance(me, Exception):
            log.warning("Error getting user balance for check: %s", me)
            await cb.answer(t(s.lang, "generic_error"), show_alert=True)
            return
        
        if not isinstance(quote, dict):
            await cb.answer(t(s.lang, "generic_error"), show_alert=True)
            return

        if s.coupon and quote.get("coupon_error"):
            await cb.answer(t_coupon_api_code(s.lang, quote.get("coupon_error")), show_alert=True)
            storage.reset_flow(cb.from_user.id)
            return
        
        # Kiểm tra số dư: tổng tiền sau khi giảm giá (nếu có coupon) <= balance
        balance = float(me.get("balance", 0) or 0)
        total = float(quote.get("total", 0) or 0)
        
        if balance < total:
            await cb.answer(
                t(s.lang, "insufficient_balance", balance=format_amount(balance), total=format_amount(total)),
                show_alert=True
            )
            storage.reset_flow(cb.from_user.id)
            return
    except Exception as e:
        log.exception("Error checking balance before checkout: %s", e)
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        return

    # ✅ LOCK ngay để chặn double click
    s.state = "buy_processing"

    # ✅ Disable nút confirm/cancel để user không bấm nữa
    await safe_edit_reply_markup(cb.message, reply_markup=None)

    idem_key = f"tg{cb.from_user.id}:{s.product_id}:{s.qty}:{cb.message.message_id}"

    try:
        telegram_user = cb.from_user.username  # Có thể là None
        resp = await order_api.checkout(
            telegram_id=cb.from_user.id,
            product_id=s.product_id,
            qty=s.qty,
            coupon=s.coupon,
            idem_key=idem_key,
            telegram_user=telegram_user,
        )

        delivery = resp.get("delivery_payload") or resp.get("delivery") or ""
        if not delivery:
            delivery = str(resp)

        # Giới hạn số dòng hiển thị trong message (max 15 dòng)
        MAX_LINES_IN_MESSAGE = 15
        delivery_lines = delivery.split('\n')
        total_lines = len([line for line in delivery_lines if line.strip()])
        
        if total_lines > MAX_LINES_IN_MESSAGE:
            # Chỉ hiển thị MAX_LINES_IN_MESSAGE dòng đầu
            shown_lines = [line for line in delivery_lines[:MAX_LINES_IN_MESSAGE] if line.strip()]
            delivery_preview = '\n'.join(shown_lines)
            delivery_note = t(s.lang, "delivery_more", shown=len(shown_lines), total=total_lines)
        else:
            delivery_preview = delivery
            delivery_note = ""

        safe_delivery_preview = html.escape(delivery_preview, quote=False)

        # Gửi thông báo với preview
        await safe_answer(
            cb.message,
            t(s.lang, "buy_ok", delivery=safe_delivery_preview, delivery_note=delivery_note),
        )
        
        # Tạo và gửi file txt (đa ngôn ngữ)
        order_code = resp.get("order_code", "ORDER")
        try:
            # Tạo file txt tạm thời với đa ngôn ngữ
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(f"{t(s.lang, 'order_file_title')}: {order_code}\n")
                f.write(f"{t(s.lang, 'order_file_delivery')}\n\n")
                f.write(delivery)
                tmp_path = f.name
            
            # Gửi file - không dùng safe_answer vì đây là document
            file_name = f"{order_code}.txt"
            try:
                await cb.message.answer_document(
                    FSInputFile(tmp_path, filename=file_name),
                    caption=t(
                        s.lang,
                        "buy_file_caption",
                        order_code=html.escape(str(order_code), quote=False),
                    )
                )
            except Exception as doc_err:
                log.warning("Failed to send document: %s", doc_err)
            
            # Xóa file tạm
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        except Exception as e:
            log.warning("Failed to send txt file: %s", e)
        
        # Answer callback ngay để giảm latency
        storage.reset_flow(cb.from_user.id)
        s = storage.get(cb.from_user.id)
        await safe_answer_callback(cb, t(s.lang, "buy_success_short"))
        
        # ✅ Reload menu ở background để không block response
        # Cache đã được clear trong order_api.checkout()
        async def reload_menu_bg():
            try:
                products = await order_api.list_products(lang=s.lang)
                await safe_answer(
                    cb.message,
                    t(s.lang, "menu_title"),
                    reply_markup=kb_products(products)
                )
            except Exception as e:
                log.warning("Failed to reload menu after purchase: %s", e)
        
        # Chạy background task để không block
        asyncio.create_task(reload_menu_bg())

    except Exception as e:
        msg = str(e)
        log.error("Checkout error: %s", msg)
        if "USER_BANNED" in msg or "http_error:403" in msg or "403" in msg:
            await safe_answer(cb.message, t(s.lang, "user_banned"))
        elif "OUT_OF_STOCK" in msg:
            await safe_answer(cb.message, t(s.lang, "out_of_stock_detail", qty="", stock_info=""))
        elif "INSUFFICIENT" in msg or "Not enough" in msg or "INSUFFICIENT_BALANCE" in msg:
            await safe_answer(cb.message, t(s.lang, "buy_not_enough"))
        elif "PRODUCT_NOT_FOUND" in msg:
            await safe_answer(cb.message, t(s.lang, "product_not_found"))
        elif "http_error:400" in msg:
            c_err = extract_error_code_from_http_runtime(msg)
            if c_err:
                await safe_answer(cb.message, t_coupon_api_code(s.lang, c_err))
            else:
                await safe_answer(cb.message, t(s.lang, "generic_error"))
        elif "server_error" in msg.lower() or "connection_error" in msg.lower():
            await safe_answer(cb.message, t(s.lang, "server_error"))
        else:
            await safe_answer(cb.message, t(s.lang, "generic_error"))

        storage.reset_flow(cb.from_user.id)
        await safe_answer_callback(cb, "Error", show_alert=False)



# ✅ CANCEL BUY
@router.callback_query(lambda c: c.data == "buy:cancel")
async def cb_buy_cancel(cb: CallbackQuery, **data):
    storage = data["storage"]
    storage.reset_flow(cb.from_user.id)
    s = storage.get(cb.from_user.id)
    await safe_answer(cb.message, t(s.lang, "buy_cancelled"))
    await safe_answer_callback(cb, t(s.lang, "cancelled"))
