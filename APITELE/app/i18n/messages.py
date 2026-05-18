MESSAGES = {
    # ══════════════════════════════════════════════════════════════════════════
    # VIETNAMESE
    # ══════════════════════════════════════════════════════════════════════════
    "vi": {
        "start": "Chào bạn! Gõ /menu để bắt đầu mua hàng.",

        "help": (
            "<b>Hướng dẫn sử dụng</b>\n\n"
            "  /menu  ·  Xem & mua sản phẩm\n"
            "  /topup  ·  Nạp tiền vào tài khoản\n"
            "  /me  ·  Xem hồ sơ & số dư\n"
            "  /history  ·  Lịch sử đơn hàng\n"
            "  /tickets  ·  Xem ticket bảo hành\n"
            "  /warranty  ·  Gửi yêu cầu bảo hành\n"
            "  /lang  ·  Đổi ngôn ngữ\n\n"
            "<i>Dùng nút nhanh bên dưới để thao tác nhanh hơn</i>"
        ),

        "menu_title": (
            "🛒  <b>STORE</b>\n\n"
            "Chọn sản phẩm hoặc gõ số thứ tự để đặt hàng"
        ),

        "product_detail": (
            "📦  <b>{name}</b>\n\n"
            "{desc}\n\n"
            "💲  <b>{price} USD</b>\n"
            "📊  Kho: <b>{stock}</b> sản phẩm"
            "{qty_discount_info}\n\n"
            "👇  Nhấn <b>Buy</b> để mua ngay"
        ),

        "qty_discount_info": "\n\n🏷  Mua <b>{min_qty}+</b> sản phẩm — giảm <b>{percent}%</b>",
        "qty_discount_tiers_info": "\n\n🏷  <b>Ưu đãi số lượng lớn:</b>\n{lines}",

        "ask_qty": (
            "<b>Nhập số lượng</b>\n\n"
            "<i>Gõ số lượng bạn muốn mua  ·  VD: 1, 5, 10</i>"
        ),

        "ask_coupon": (
            "<b>Mã giảm giá</b>\n\n"
            "Nhập mã coupon hoặc gõ /skip để bỏ qua"
        ),

        "coupon_applied": "✅  Đã áp dụng: <b>{coupon}</b>",
        "coupon_invalid": "Mã không hợp lệ hoặc đã hết hạn.",
        "coupon_err_invalid": "Mã không tồn tại. Thử lại hoặc /skip",
        "coupon_err_expired": "Mã đã hết hạn. Thử mã khác hoặc /skip",
        "coupon_err_inactive": "Mã đã bị vô hiệu. Liên hệ admin hoặc /skip",
        "coupon_err_not_started": "Mã chưa đến thời gian áp dụng. Thử lại sau hoặc /skip",
        "coupon_err_wrong_product": "Mã không áp dụng cho sản phẩm này. /skip hoặc đổi SP",
        "coupon_err_wrong_user": "Mã này không dành cho tài khoản của bạn",
        "coupon_err_already_used": "Bạn đã hết lượt dùng mã này",
        "coupon_err_max_uses": "Mã đã hết lượt sử dụng",
        "coupon_err_min_order": "Đơn chưa đủ giá trị tối thiểu để dùng mã",
        "coupon_err_max_qty": "Số lượng vượt giới hạn của mã (giảm SL hoặc /skip)",

        "quote": (
            "<b>Xác nhận đơn hàng</b>\n\n"
            "  Tạm tính        {subtotal} USD\n"
            "  Giảm giá       -{discount} USD\n"
            "  Coupon          {coupon}\n"
            "  ─────────────\n"
            "  <b>Tổng            {total} USD</b>\n\n"
            "<i>Nhấn</i> ✅ <i>để thanh toán</i>"
        ),

        "buy_ok": (
            "🎉  <b>Thanh toán thành công!</b>\n\n"
            "<code>{delivery}</code>\n\n"
            "{delivery_note}"
            "<i>Xem file đính kèm bên dưới</i>"
        ),

        "order_file_title": "Đơn hàng",
        "order_file_delivery": "Thông tin nhận hàng:",
        "delivery_more": "<i>Hiển thị {shown}/{total} items — xem file đính kèm</i>",

        "buy_not_enough": (
            "⚠️  <b>Số dư không đủ</b>\n\n"
            "Gõ /topup để nạp thêm tiền"
        ),

        "topup_choose_method": (
            "💳  <b>Nạp tiền</b>\n\n"
            "Chọn phương thức thanh toán bên dưới"
        ),

        "topup_ask_amount": (
            "<b>Nhập số tiền nạp</b>\n\n"
            "<i>Gõ số tiền USD  ·  VD: 5, 10, 50</i>"
        ),

        "topup_invoice": (
            "📋  <b>Hóa đơn nạp tiền</b>\n\n"
            "  Network    <b>{network}</b>\n"
            "  Coin          <b>{coin}</b>\n"
            "  Amount     <b>{amount}</b>\n\n"
            "Địa chỉ ví:\n"
            "<code>{address}</code>\n\n"
            "⚠️  Chỉ gửi đúng network/coin\n"
            "<i>Bot sẽ tự xác nhận khi nhận được</i>"
        ),

        "topup_exchange_fee_warning": (
            "⚠️  <b>Lưu ý phí giao dịch</b>\n\n"
            "Bạn cần chuyển thêm phí sàn để Bot nhận đủ.\n"
            "Nạp <b>{amount} USD</b> → chuyển <b>{amount} + phí sàn</b>"
        ),

        "topup_success": (
            "🎉  <b>Nạp tiền thành công!</b>\n\n"
            "Số dư đã được cập nhật\n"
            "ID: <code>{topup_id}</code>"
        ),

        "topup_pending": (
            "⏳  <b>Đang chờ thanh toán</b>\n\n"
            "ID: <code>{topup_id}</code>\n"
            "Hiệu lực: 30 phút\n\n"
            "<i>Bot sẽ tự động thông báo khi nhận được</i>"
        ),

        "topup_pending_exists": (
            "⚠️  <b>Bạn có topup đang chờ</b>\n\n"
            "ID: <code>{topup_id}</code>\n"
            "Hết hạn: {expire_time}\n\n"
            "Nhấn <b>Cancel</b> để hủy và tạo mới"
        ),

        "topup_cancelled": "✅  Đã hủy topup. Gõ /topup để tạo mới.",

        "topup_failed": (
            "❌  <b>Topup thất bại / hết hạn</b>\n"
            "ID: <code>{topup_id}</code>"
        ),

        "topup_binance_pay_invoice": (
            "🟠  <b>Binance ID Pay (P2P)</b>\n\n"
            "Gửi USDT từ Binance App đến:\n\n"
            "  Binance ID\n"
            "  <code>{binance_id}</code>\n\n"
            "  Note <i>(bắt buộc)</i>\n"
            "  <code>{note}</code>\n\n"
            "  Số tiền: <b>{amount} USDT</b>\n\n"
            "⚠️  <b>PHẢI điền đúng Note</b>\n"
            "Thiếu Note = không khớp được đơn nạp\n\n"
            "<i>Tự động cộng tiền ~30 giây sau khi gửi</i>"
        ),

        "me": "👤  <b>Profile</b>\n- ID: <code>{tid}</code>\n- @{username}\n- Lang: <b>{user_lang}</b>",

        "me_format": (
            "👤  <b>Tài khoản</b>\n\n"
            "  ID              <code>{tid}</code>\n"
            "  Username   @{username}\n"
            "  Ngôn ngữ  {user_lang}\n\n"
            "  💰  Số dư     <b>{balance} {currency}</b>\n\n"
            "<i>/topup để nạp thêm  ·  /menu để mua hàng</i>"
        ),

        "history_title": "📜  <b>Lịch sử</b>\n{items}",

        "history_choose_month": (
            "📅  <b>Lịch sử đơn hàng</b>\n\n"
            "<i>Chọn tháng để xem</i>"
        ),

        "history_list_title": (
            "📅  <b>Đơn hàng {month}/{year}</b>\n\n"
            "Tổng: {total} đơn\n\n"
            "<i>Chọn đơn để xem chi tiết</i>"
        ),

        "history_no_orders": "Không có đơn hàng nào trong tháng này.",

        "history_order_detail": (
            "📦  <b>Chi tiết đơn hàng</b>\n\n"
            "  Mã đơn        <code>{order_code}</code>\n"
            "  Sản phẩm    {product_name}\n"
            "  Số lượng      {qty}\n"
            "  Đơn giá        {unit_price} {currency}\n\n"
            "  Tạm tính      {subtotal} {currency}\n"
            "  Giảm giá     -{discount_total} {currency}\n"
            "  Coupon        {coupon_code}\n"
            "  ─────────────\n"
            "  <b>Tổng            {total} {currency}</b>\n\n"
            "  Trạng thái    <b>{status}</b>\n"
            "  Ngày tạo      {created_at}"
        ),

        "ticket_ask": "Mô tả lỗi/bảo hành và có thể gửi kèm ảnh.",
        "ticket_ok": "✅  Đã tạo ticket: <code>{ticket_id}</code>",
        "error_no_orders": "Không có đơn hàng nào để bảo hành.",

        "error_select_order_title": (
            "🛡  <b>Bảo hành</b>\n\n"
            "Tổng: {total} đơn\n\n"
            "<i>Chọn đơn hàng cần bảo hành</i>"
        ),

        "error_ask_reason": (
            "📦  <b>Thông tin đơn hàng</b>\n\n"
            "  Mã đơn    <code>{order_code}</code>\n"
            "  SP            {product_name}\n"
            "  SL             {qty}\n"
            "  Tổng         {total} {currency}"
        ),

        "error_enter_reason": (
            "<b>Nhập lý do bảo hành</b>\n\n"
            "<i>VD: Sản phẩm bị lỗi, không hoạt động, thiếu hàng...</i>"
        ),

        "error_enter_reason_with_photo": (
            "<b>Nhập lý do bảo hành</b>\n\n"
            "Bạn có thể gửi kèm ảnh chụp lỗi\n"
            "<i>VD: Sản phẩm bị lỗi, không hoạt động, thiếu hàng...</i>"
        ),

        "error_photo_saved": "📸  Đã lưu ảnh. Bây giờ hãy nhập lý do:",

        "error_reason_empty": "Lý do không được để trống.",

        "error_confirm_with_reason": (
            "🛡  <b>Xác nhận bảo hành</b>\n\n"
            "  Mã đơn    <code>{order_code}</code>\n"
            "  SP            {product_name}\n"
            "  SL  {qty}  ·  Tổng  {total} {currency}\n\n"
            "  <b>Lý do:</b>\n"
            "  {reason}\n\n"
            "<i>Nhấn</i> ✅ <i>để gửi</i>"
        ),

        "error_ticket_created": (
            "✅  <b>Đã gửi yêu cầu bảo hành</b>\n\n"
            "Ticket: <code>{ticket_id}</code>\n\n"
            "<i>Dùng /tickets để theo dõi trạng thái</i>"
        ),

        "error_ticket_created_short": "✅  Đã gửi bảo hành",
        "error_cancelled": "Đã hủy yêu cầu bảo hành.",
        "cancelled": "Đã hủy",

        "tickets_title": (
            "🎫  <b>Ticket bảo hành</b>\n\n"
            "Tổng: {total} ticket\n\n"
            "<i>Chọn ticket để xem chi tiết</i>"
        ),

        "tickets_empty": "Chưa có ticket bảo hành nào.\n\n<i>Dùng /warranty để tạo yêu cầu mới</i>",

        "tickets_detail": (
            "🎫  <b>Chi tiết ticket</b>\n\n"
            "  Ticket         <code>{ticket_id}</code>\n"
            "  Mã đơn     <code>{order_code}</code>\n"
            "  Trạng thái  <b>{status}</b>\n\n"
            "  <b>Nội dung:</b>\n"
            "  {text}\n\n"
            "  Ngày tạo    {created_at}"
            "{replacement_info}"
        ),

        "tickets_replacement": "\n\n🎁  <b>Hàng thay thế:</b>\n<code>{items}</code>",

        "buy_file_caption": "Đơn hàng {order_code}",

        "lang_choose": (
            "🌐  <b>Ngôn ngữ</b>\n\n"
            "<i>Chọn ngôn ngữ hiển thị</i>"
        ),

        "generic_error": "Có lỗi xảy ra. Vui lòng thử lại.",
        "user_banned": "Tài khoản đã bị khóa. Liên hệ admin để được hỗ trợ.",
        "none_coupon": "Không có",
        "flood_warning": "Bạn gửi nhanh quá — chờ 2-3 giây nhé.",
        "spam_blocked": "Tạm chặn {minutes} phút do spam.",

        "btn_products": "🛍 Cửa hàng",
        "btn_balance": "💰 Số dư",
        "btn_refresh": "🔄 Làm mới",
        "btn_payment": "💳 Nạp tiền",
        "btn_help": "📖 Hướng dẫn",
        "placeholder_quick_buttons": "Chọn nút bên dưới hoặc gõ lệnh...",

        "welcome_title": "🛍  <b>Chào mừng đến với Shop</b>",

        "welcome_features": (
            "✦  Xem & mua sản phẩm tự động\n"
            "✦  Nạp tiền crypto đa mạng\n"
            "✦  Tra cứu lịch sử đơn hàng\n"
            "✦  Bảo hành & hỗ trợ nhanh"
        ),

        "welcome_commands": (
            "<b>Lệnh chính:</b>\n\n"
            "  /menu  ·  Cửa hàng\n"
            "  /topup  ·  Nạp tiền\n"
            "  /me  ·  Tài khoản\n"
            "  /history  ·  Lịch sử\n"
            "  /tickets  ·  Ticket bảo hành\n"
            "  /warranty  ·  Gửi bảo hành\n"
            "  /lang  ·  Đổi ngôn ngữ"
        ),

        "welcome_tip": "<i>Dùng nút nhanh bên dưới để thao tác tiện hơn</i>",

        "out_of_stock_detail": (
            "⚠️  <b>Không đủ hàng trong kho</b>\n\n"
            "Bạn chọn: {qty} item{stock_info}\n\n"
            "<i>Giảm số lượng hoặc /menu để chọn lại</i>"
        ),

        "product_not_found": "Sản phẩm không tồn tại hoặc đã ngừng bán.",

        "insufficient_balance": (
            "⚠️  <b>Không đủ số dư</b>\n\n"
            "  Số dư     {balance} USD\n"
            "  Cần        {total} USD\n\n"
            "<i>/topup để nạp thêm</i>"
        ),

        "invalid_data": "Dữ liệu không hợp lệ.",
        "server_error": "Lỗi kết nối server. Thử lại sau.",
        "cancel_flow": "Đã hủy thao tác trước đó.",
        "buy_cancelled": "Đã hủy giao dịch. /menu để chọn lại.",

        "payment_check": (
            "💳  <b>Kiểm tra thanh toán</b>\n\n"
            "  /topup  ·  Xem topup đang chờ\n"
            "  /history  ·  Lịch sử giao dịch"
        ),

        "buy_success_short": "✅  Mua thành công!",
        "lang_changed": "✅  Đã đổi sang {lang}",
        "keyboard_updated": "Đã cập nhật bàn phím.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ENGLISH
    # ══════════════════════════════════════════════════════════════════════════
    "en": {
        "start": "Welcome! Type /menu to start shopping.",

        "help": (
            "<b>Help & Commands</b>\n\n"
            "  /menu  ·  Browse & buy products\n"
            "  /topup  ·  Add balance\n"
            "  /me  ·  Profile & balance\n"
            "  /history  ·  Order history\n"
            "  /tickets  ·  Warranty tickets\n"
            "  /warranty  ·  Submit warranty\n"
            "  /lang  ·  Change language\n\n"
            "<i>Use quick buttons below for faster access</i>"
        ),

        "menu_title": (
            "🛒  <b>STORE</b>\n\n"
            "Tap a product or type its number to order"
        ),

        "product_detail": (
            "📦  <b>{name}</b>\n\n"
            "{desc}\n\n"
            "💲  <b>{price} USD</b>\n"
            "📊  Stock: <b>{stock}</b> available"
            "{qty_discount_info}\n\n"
            "👇  Tap <b>Buy</b> to order now"
        ),

        "qty_discount_info": "\n\n🏷  Buy <b>{min_qty}+</b> items — save <b>{percent}%</b>",
        "qty_discount_tiers_info": "\n\n🏷  <b>Bulk pricing:</b>\n{lines}",

        "ask_qty": (
            "<b>Enter quantity</b>\n\n"
            "<i>Type how many you want  ·  e.g. 1, 5, 10</i>"
        ),

        "ask_coupon": (
            "<b>Discount code</b>\n\n"
            "Enter your coupon or type /skip"
        ),

        "coupon_applied": "✅  Applied: <b>{coupon}</b>",
        "coupon_invalid": "Invalid or expired code.",
        "coupon_err_invalid": "Code not found. Try again or /skip",
        "coupon_err_expired": "Code has expired. Try another or /skip",
        "coupon_err_inactive": "Code is disabled. Contact admin or /skip",
        "coupon_err_not_started": "Code is not active yet. Try later or /skip",
        "coupon_err_wrong_product": "Code doesn't apply to this product. /skip or pick another",
        "coupon_err_wrong_user": "This code is not for your account",
        "coupon_err_already_used": "You've reached usage limit for this code",
        "coupon_err_max_uses": "Code has no redemptions left",
        "coupon_err_min_order": "Order below minimum for this code",
        "coupon_err_max_qty": "Quantity exceeds code limit (lower qty or /skip)",

        "quote": (
            "<b>Order Summary</b>\n\n"
            "  Subtotal       {subtotal} USD\n"
            "  Discount      -{discount} USD\n"
            "  Coupon         {coupon}\n"
            "  ─────────────\n"
            "  <b>Total            {total} USD</b>\n\n"
            "<i>Tap</i> ✅ <i>to confirm payment</i>"
        ),

        "buy_ok": (
            "🎉  <b>Payment successful!</b>\n\n"
            "<code>{delivery}</code>\n\n"
            "{delivery_note}"
            "<i>See attached file below</i>"
        ),

        "order_file_title": "Order",
        "order_file_delivery": "Delivery information:",
        "delivery_more": "<i>Showing {shown}/{total} items — see attached file</i>",

        "buy_not_enough": (
            "⚠️  <b>Insufficient balance</b>\n\n"
            "Type /topup to add funds"
        ),

        "topup_choose_method": (
            "💳  <b>Top Up</b>\n\n"
            "Choose a payment method below"
        ),

        "topup_ask_amount": (
            "<b>Enter amount</b>\n\n"
            "<i>Type the USD amount  ·  e.g. 5, 10, 50</i>"
        ),

        "topup_invoice": (
            "📋  <b>Topup Invoice</b>\n\n"
            "  Network    <b>{network}</b>\n"
            "  Coin          <b>{coin}</b>\n"
            "  Amount     <b>{amount}</b>\n\n"
            "Wallet address:\n"
            "<code>{address}</code>\n\n"
            "⚠️  Send only via correct network/coin\n"
            "<i>Bot will confirm automatically</i>"
        ),

        "topup_exchange_fee_warning": (
            "⚠️  <b>Transaction fee notice</b>\n\n"
            "Add exchange fee so Bot receives the full amount.\n"
            "Top up <b>{amount} USD</b> → send <b>{amount} + exchange fee</b>"
        ),

        "topup_success": (
            "🎉  <b>Topup successful!</b>\n\n"
            "Balance has been updated\n"
            "ID: <code>{topup_id}</code>"
        ),

        "topup_pending": (
            "⏳  <b>Waiting for payment</b>\n\n"
            "ID: <code>{topup_id}</code>\n"
            "Valid for: 30 minutes\n\n"
            "<i>Bot will notify you automatically</i>"
        ),

        "topup_pending_exists": (
            "⚠️  <b>Pending topup exists</b>\n\n"
            "ID: <code>{topup_id}</code>\n"
            "Expires: {expire_time}\n\n"
            "Press <b>Cancel</b> to cancel and create new"
        ),

        "topup_cancelled": "✅  Cancelled. You can /topup again.",

        "topup_failed": (
            "❌  <b>Topup failed / expired</b>\n"
            "ID: <code>{topup_id}</code>"
        ),

        "topup_binance_pay_invoice": (
            "🟠  <b>Binance ID Pay (P2P)</b>\n\n"
            "Send USDT from Binance App to:\n\n"
            "  Binance ID\n"
            "  <code>{binance_id}</code>\n\n"
            "  Note <i>(required)</i>\n"
            "  <code>{note}</code>\n\n"
            "  Amount: <b>{amount} USDT</b>\n\n"
            "⚠️  <b>You MUST include the Note</b>\n"
            "Missing note = deposit cannot be matched\n\n"
            "<i>Auto-credit ~30 seconds after sending</i>"
        ),

        "me": "👤  <b>Profile</b>\n- ID: <code>{tid}</code>\n- @{username}\n- Lang: <b>{user_lang}</b>",

        "me_format": (
            "👤  <b>Your Account</b>\n\n"
            "  ID              <code>{tid}</code>\n"
            "  Username   @{username}\n"
            "  Language    {user_lang}\n\n"
            "  💰  Balance  <b>{balance} {currency}</b>\n\n"
            "<i>/topup to add funds  ·  /menu to shop</i>"
        ),

        "history_title": "📜  <b>History</b>\n{items}",

        "history_choose_month": (
            "📅  <b>Order History</b>\n\n"
            "<i>Select a month</i>"
        ),

        "history_list_title": (
            "📅  <b>Orders {month}/{year}</b>\n\n"
            "Total: {total} orders\n\n"
            "<i>Select an order for details</i>"
        ),

        "history_no_orders": "No orders this month.",

        "history_order_detail": (
            "📦  <b>Order Details</b>\n\n"
            "  Code           <code>{order_code}</code>\n"
            "  Product      {product_name}\n"
            "  Quantity     {qty}\n"
            "  Unit price   {unit_price} {currency}\n\n"
            "  Subtotal     {subtotal} {currency}\n"
            "  Discount    -{discount_total} {currency}\n"
            "  Coupon       {coupon_code}\n"
            "  ─────────────\n"
            "  <b>Total           {total} {currency}</b>\n\n"
            "  Status         <b>{status}</b>\n"
            "  Created       {created_at}"
        ),

        "ticket_ask": "Describe your issue and optionally attach a photo.",
        "ticket_ok": "✅  Ticket created: <code>{ticket_id}</code>",
        "error_no_orders": "No orders available for warranty.",

        "error_select_order_title": (
            "🛡  <b>Warranty</b>\n\n"
            "Total: {total} orders\n\n"
            "<i>Select an order for warranty</i>"
        ),

        "error_ask_reason": (
            "📦  <b>Order Info</b>\n\n"
            "  Code       <code>{order_code}</code>\n"
            "  Product  {product_name}\n"
            "  Qty          {qty}\n"
            "  Total       {total} {currency}"
        ),

        "error_enter_reason": (
            "<b>Enter warranty reason</b>\n\n"
            "<i>e.g. Product defective, not working, missing items...</i>"
        ),

        "error_enter_reason_with_photo": (
            "<b>Enter warranty reason</b>\n\n"
            "You can also attach a photo\n"
            "<i>e.g. Product defective, not working, missing items...</i>"
        ),

        "error_photo_saved": "📸  Photo saved. Now enter the reason:",

        "error_reason_empty": "Reason cannot be empty.",

        "error_confirm_with_reason": (
            "🛡  <b>Confirm Warranty</b>\n\n"
            "  Code       <code>{order_code}</code>\n"
            "  Product  {product_name}\n"
            "  Qty  {qty}  ·  Total  {total} {currency}\n\n"
            "  <b>Reason:</b>\n"
            "  {reason}\n\n"
            "<i>Tap</i> ✅ <i>to submit</i>"
        ),

        "error_ticket_created": (
            "✅  <b>Warranty submitted</b>\n\n"
            "Ticket: <code>{ticket_id}</code>\n\n"
            "<i>Use /tickets to track status</i>"
        ),

        "error_ticket_created_short": "✅  Warranty submitted",
        "error_cancelled": "Warranty request cancelled.",
        "cancelled": "Cancelled",

        "tickets_title": (
            "🎫  <b>Warranty Tickets</b>\n\n"
            "Total: {total} tickets\n\n"
            "<i>Select a ticket for details</i>"
        ),

        "tickets_empty": "No warranty tickets yet.\n\n<i>Use /warranty to submit a new request</i>",

        "tickets_detail": (
            "🎫  <b>Ticket Details</b>\n\n"
            "  Ticket       <code>{ticket_id}</code>\n"
            "  Order        <code>{order_code}</code>\n"
            "  Status       <b>{status}</b>\n\n"
            "  <b>Content:</b>\n"
            "  {text}\n\n"
            "  Created    {created_at}"
            "{replacement_info}"
        ),

        "tickets_replacement": "\n\n🎁  <b>Replacement items:</b>\n<code>{items}</code>",

        "buy_file_caption": "Order {order_code}",

        "lang_choose": (
            "🌐  <b>Language</b>\n\n"
            "<i>Choose display language</i>"
        ),

        "generic_error": "Something went wrong. Please try again.",
        "user_banned": "Account banned. Contact admin for support.",
        "none_coupon": "None",
        "flood_warning": "Too many messages — please wait 2-3 seconds.",
        "spam_blocked": "Blocked {minutes} minutes for spam.",

        "btn_products": "🛍 Store",
        "btn_balance": "💰 Balance",
        "btn_refresh": "🔄 Refresh",
        "btn_payment": "💳 Top Up",
        "btn_help": "📖 Help",
        "placeholder_quick_buttons": "Tap a button or type a command...",

        "welcome_title": "🛍  <b>Welcome to the Shop</b>",

        "welcome_features": (
            "✦  Browse & buy products instantly\n"
            "✦  Crypto top-up (multi-chain)\n"
            "✦  Full order history\n"
            "✦  Quick warranty support"
        ),

        "welcome_commands": (
            "<b>Commands:</b>\n\n"
            "  /menu  ·  Store\n"
            "  /topup  ·  Top up\n"
            "  /me  ·  Account\n"
            "  /history  ·  History\n"
            "  /tickets  ·  Warranty tickets\n"
            "  /warranty  ·  Submit warranty\n"
            "  /lang  ·  Language"
        ),

        "welcome_tip": "<i>Use quick buttons below for faster actions</i>",

        "out_of_stock_detail": (
            "⚠️  <b>Insufficient stock</b>\n\n"
            "You selected: {qty} items{stock_info}\n\n"
            "<i>Lower quantity or /menu to pick again</i>"
        ),

        "product_not_found": "Product not found or discontinued.",

        "insufficient_balance": (
            "⚠️  <b>Insufficient balance</b>\n\n"
            "  Balance    {balance} USD\n"
            "  Required  {total} USD\n\n"
            "<i>/topup to add funds</i>"
        ),

        "invalid_data": "Invalid data.",
        "server_error": "Server error. Please try again later.",
        "cancel_flow": "Previous action cancelled.",
        "buy_cancelled": "Transaction cancelled. /menu to start over.",

        "payment_check": (
            "💳  <b>Check Payment</b>\n\n"
            "  /topup  ·  Check pending topup\n"
            "  /history  ·  Transaction history"
        ),

        "buy_success_short": "✅  Purchase successful!",
        "lang_changed": "✅  Changed to {lang}",
        "keyboard_updated": "Keyboard updated.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # RUSSIAN
    # ══════════════════════════════════════════════════════════════════════════
    "ru": {
        "start": "Привет! /menu — начать покупки.",

        "help": (
            "<b>Помощь</b>\n\n"
            "  /menu  ·  Товары\n"
            "  /topup  ·  Пополнить\n"
            "  /me  ·  Профиль\n"
            "  /history  ·  История\n"
            "  /tickets  ·  Тикеты\n"
            "  /warranty  ·  Гарантия\n"
            "  /lang  ·  Язык\n\n"
            "<i>Используйте кнопки внизу</i>"
        ),

        "menu_title": (
            "🛒  <b>МАГАЗИН</b>\n\n"
            "Нажмите на товар или введите номер"
        ),

        "product_detail": (
            "📦  <b>{name}</b>\n\n"
            "{desc}\n\n"
            "💲  <b>{price} USD</b>\n"
            "📊  Наличие: <b>{stock}</b>"
            "{qty_discount_info}\n\n"
            "👇  Нажмите <b>Buy</b>"
        ),

        "qty_discount_info": "\n\n🏷  От <b>{min_qty}</b> шт. — скидка <b>{percent}%</b>",
        "qty_discount_tiers_info": "\n\n🏷  <b>Оптовые скидки:</b>\n{lines}",
        "ask_qty": "<b>Введите количество</b>\n\n<i>Например: 1, 5, 10</i>",
        "ask_coupon": "<b>Код скидки</b>\n\nВведите код или /skip",
        "coupon_applied": "✅  Применён: <b>{coupon}</b>",
        "coupon_invalid": "Недействительный код.",
        "coupon_err_invalid": "Код не найден. Повторите или /skip",
        "coupon_err_expired": "Код истёк. Другой или /skip",
        "coupon_err_inactive": "Код отключён. Свяжитесь с админом или /skip",
        "coupon_err_not_started": "Код ещё не активен. Позже или /skip",
        "coupon_err_wrong_product": "Код не для этого товара. /skip или другой товар",
        "coupon_err_wrong_user": "Код не для вашего аккаунта",
        "coupon_err_already_used": "Лимит использований исчерпан",
        "coupon_err_max_uses": "Код полностью использован",
        "coupon_err_min_order": "Сумма ниже минимума для кода",
        "coupon_err_max_qty": "Количество превышает лимит кода (уменьшите или /skip)",

        "quote": (
            "<b>Итого заказа</b>\n\n"
            "  Подытог      {subtotal} USD\n"
            "  Скидка        -{discount} USD\n"
            "  Купон          {coupon}\n"
            "  ─────────────\n"
            "  <b>Итого          {total} USD</b>\n\n"
            "<i>Нажмите</i> ✅"
        ),

        "buy_ok": "🎉  <b>Оплата успешна!</b>\n\n<code>{delivery}</code>\n\n{delivery_note}<i>См. файл ниже</i>",
        "order_file_title": "Заказ",
        "order_file_delivery": "Информация о доставке:",
        "delivery_more": "<i>Показано {shown}/{total} — полный список в файле</i>",
        "buy_not_enough": "⚠️  <b>Недостаточно средств</b>\n\n/topup для пополнения",

        "topup_choose_method": "💳  <b>Пополнение</b>\n\n<i>Выберите метод оплаты</i>",
        "topup_ask_amount": "<b>Введите сумму</b>\n\n<i>Например: 5, 10, 50</i>",

        "topup_invoice": (
            "📋  <b>Счёт</b>\n\n"
            "  Сеть       <b>{network}</b>\n"
            "  Монета  <b>{coin}</b>\n"
            "  Сумма   <b>{amount}</b>\n\n"
            "Адрес:\n<code>{address}</code>\n\n"
            "⚠️  Только правильная сеть/монета\n"
            "<i>Бот подтвердит автоматически</i>"
        ),

        "topup_exchange_fee_warning": "⚠️  <b>Комиссия</b>\n\nДобавьте комиссию биржи.\n{amount} USD → отправьте {amount} + комиссия",
        "topup_success": "🎉  <b>Пополнение успешно!</b>\n\nБаланс обновлён\nID: <code>{topup_id}</code>",
        "topup_pending": "⏳  <b>Ожидание оплаты</b>\n\nID: <code>{topup_id}</code>\nДействует: 30 минут\n\n<i>Бот уведомит автоматически</i>",
        "topup_pending_exists": "⚠️  <b>Ожидающее пополнение</b>\n\nID: <code>{topup_id}</code>\nИстекает: {expire_time}\n\n<b>Cancel</b> для отмены",
        "topup_cancelled": "✅  Отменено. /topup снова.",
        "topup_failed": "❌  <b>Не удалось / истекло</b>\nID: <code>{topup_id}</code>",

        "topup_binance_pay_invoice": (
            "🟠  <b>Binance ID Pay (P2P)</b>\n\n"
            "Отправьте USDT из Binance App:\n\n"
            "  Binance ID\n  <code>{binance_id}</code>\n\n"
            "  Примечание <i>(обязательно)</i>\n  <code>{note}</code>\n\n"
            "  Сумма: <b>{amount} USDT</b>\n\n"
            "⚠️  <b>Обязательно укажите примечание</b>\n\n"
            "<i>Авто-зачисление ~30 секунд</i>"
        ),

        "me": "👤  <b>Профиль</b>\n- ID: <code>{tid}</code>\n- @{username}\n- Язык: <b>{user_lang}</b>",
        "me_format": "👤  <b>Ваш аккаунт</b>\n\n  ID              <code>{tid}</code>\n  Username   @{username}\n  Язык          {user_lang}\n\n  💰  Баланс  <b>{balance} {currency}</b>\n\n<i>/topup  ·  /menu</i>",
        "history_title": "📜  <b>История</b>\n{items}",
        "history_choose_month": "📅  <b>История заказов</b>\n\n<i>Выберите месяц</i>",
        "history_list_title": "📅  <b>Заказы {month}/{year}</b>\n\nВсего: {total}\n\n<i>Выберите заказ</i>",
        "history_no_orders": "Нет заказов за этот месяц.",
        "history_order_detail": "📦  <b>Детали заказа</b>\n\n  Код           <code>{order_code}</code>\n  Товар       {product_name}\n  Кол-во     {qty}\n  Цена         {unit_price} {currency}\n\n  Подытог   {subtotal} {currency}\n  Скидка     -{discount_total} {currency}\n  Купон       {coupon_code}\n  ─────────────\n  <b>Итого        {total} {currency}</b>\n\n  Статус      <b>{status}</b>\n  Создан     {created_at}",
        "ticket_ask": "Опишите проблему и прикрепите фото.",
        "ticket_ok": "✅  Тикет: <code>{ticket_id}</code>",
        "error_no_orders": "Нет заказов для гарантии.",
        "error_select_order_title": "🛡  <b>Гарантия</b>\n\nВсего: {total}\n\n<i>Выберите заказ</i>",
        "error_ask_reason": "📦  <b>Заказ</b>\n\n  Код        <code>{order_code}</code>\n  Товар   {product_name}\n  Кол-во  {qty}\n  Итого    {total} {currency}",
        "error_enter_reason": "<b>Введите причину</b>\n\n<i>Пример: Товар неисправен, не работает...</i>",
        "error_enter_reason_with_photo": "<b>Введите причину</b>\n\nМожно прикрепить фото\n<i>Пример: Товар неисправен, не работает...</i>",
        "error_photo_saved": "📸  Фото сохранено. Введите причину:",
        "error_reason_empty": "Причина не может быть пустой.",
        "error_confirm_with_reason": "🛡  <b>Подтверждение</b>\n\n  Код        <code>{order_code}</code>\n  Товар   {product_name}\n  Кол-во  {qty}  ·  Итого  {total} {currency}\n\n  <b>Причина:</b>\n  {reason}\n\n<i>Нажмите</i> ✅",
        "error_ticket_created": "✅  <b>Тикет создан</b>\n\nТикет: <code>{ticket_id}</code>\n\n<i>/tickets для отслеживания</i>",
        "error_ticket_created_short": "✅  Тикет создан",
        "error_cancelled": "Запрос отменён.",
        "cancelled": "Отменено",
        "tickets_title": "🎫  <b>Тикеты</b>\n\nВсего: {total}\n\n<i>Выберите тикет</i>",
        "tickets_empty": "Нет тикетов.\n\n<i>/warranty для создания</i>",
        "tickets_detail": "🎫  <b>Детали тикета</b>\n\n  Тикет       <code>{ticket_id}</code>\n  Заказ       <code>{order_code}</code>\n  Статус     <b>{status}</b>\n\n  <b>Содержание:</b>\n  {text}\n\n  Создан    {created_at}{replacement_info}",
        "tickets_replacement": "\n\n🎁  <b>Замена:</b>\n<code>{items}</code>",
        "buy_file_caption": "Заказ {order_code}",
        "lang_choose": "🌐  <b>Язык</b>\n\n<i>Выберите язык</i>",
        "generic_error": "Ошибка. Попробуйте ещё раз.",
        "user_banned": "Аккаунт заблокирован. Свяжитесь с админом.",
        "none_coupon": "Нет",
        "flood_warning": "Слишком быстро — подождите 2-3 секунды.",
        "spam_blocked": "Блокировка {minutes} мин. за спам.",
        "btn_products": "🛍 Магазин",
        "btn_balance": "💰 Баланс",
        "btn_refresh": "🔄 Обновить",
        "btn_payment": "💳 Пополнить",
        "btn_help": "📖 Помощь",
        "placeholder_quick_buttons": "Кнопка или команда...",
        "welcome_title": "🛍  <b>Добро пожаловать</b>",
        "welcome_features": "✦  Просмотр и покупка\n✦  Крипто-пополнение\n✦  История заказов\n✦  Гарантия",
        "welcome_commands": "<b>Команды:</b>\n\n  /menu  ·  Магазин\n  /topup  ·  Пополнить\n  /me  ·  Аккаунт\n  /history  ·  История\n  /tickets  ·  Тикеты\n  /warranty  ·  Гарантия\n  /lang  ·  Язык",
        "welcome_tip": "<i>Используйте кнопки внизу</i>",
        "out_of_stock_detail": "⚠️  <b>Недостаточно товара</b>\n\nВыбрано: {qty} шт.{stock_info}\n\n<i>Уменьшите или /menu</i>",
        "product_not_found": "Товар не найден.",
        "insufficient_balance": "⚠️  <b>Недостаточно средств</b>\n\n  Баланс    {balance} USD\n  Нужно     {total} USD\n\n<i>/topup</i>",
        "invalid_data": "Неверные данные.",
        "server_error": "Ошибка сервера. Попробуйте позже.",
        "cancel_flow": "Действие отменено.",
        "buy_cancelled": "Транзакция отменена. /menu",
        "payment_check": "💳  <b>Проверка оплаты</b>\n\n  /topup  ·  Ожидающие\n  /history  ·  История",
        "buy_success_short": "✅  Покупка успешна!",
        "lang_changed": "✅  Язык: {lang}",
        "keyboard_updated": "Клавиатура обновлена.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CHINESE
    # ══════════════════════════════════════════════════════════════════════════
    "zh": {
        "start": "你好！/menu 开始购物。",

        "help": (
            "<b>帮助</b>\n\n"
            "  /menu  ·  商品\n"
            "  /topup  ·  充值\n"
            "  /me  ·  个人资料\n"
            "  /history  ·  历史\n"
            "  /tickets  ·  工单\n"
            "  /warranty  ·  保修\n"
            "  /lang  ·  语言\n\n"
            "<i>使用下方快捷按钮</i>"
        ),

        "menu_title": (
            "🛒  <b>商店</b>\n\n"
            "点击商品或输入编号下单"
        ),

        "product_detail": (
            "📦  <b>{name}</b>\n\n"
            "{desc}\n\n"
            "💲  <b>{price} USD</b>\n"
            "📊  库存: <b>{stock}</b>"
            "{qty_discount_info}\n\n"
            "👇  点击 <b>Buy</b> 立即购买"
        ),

        "qty_discount_info": "\n\n🏷  购买 <b>{min_qty}+</b> 件 — 享 <b>{percent}%</b> 折扣",
        "qty_discount_tiers_info": "\n\n🏷  <b>批量优惠:</b>\n{lines}",
        "ask_qty": "<b>输入数量</b>\n\n<i>例如: 1, 5, 10</i>",
        "ask_coupon": "<b>优惠码</b>\n\n输入代码或 /skip",
        "coupon_applied": "✅  已应用: <b>{coupon}</b>",
        "coupon_invalid": "无效或过期的代码。",
        "coupon_err_invalid": "代码不存在。重试或 /skip",
        "coupon_err_expired": "代码已过期。换码或 /skip",
        "coupon_err_inactive": "代码已停用。联系管理员或 /skip",
        "coupon_err_not_started": "代码尚未生效。稍后或 /skip",
        "coupon_err_wrong_product": "代码不适用于此商品。/skip 或换商品",
        "coupon_err_wrong_user": "代码不适用于您的账户",
        "coupon_err_already_used": "已达到使用上限",
        "coupon_err_max_uses": "代码已用完",
        "coupon_err_min_order": "订单金额未达最低要求",
        "coupon_err_max_qty": "数量超过代码限制 (减少或 /skip)",

        "quote": (
            "<b>订单确认</b>\n\n"
            "  小计          {subtotal} USD\n"
            "  折扣         -{discount} USD\n"
            "  优惠券      {coupon}\n"
            "  ─────────────\n"
            "  <b>总计          {total} USD</b>\n\n"
            "<i>点击</i> ✅ <i>确认</i>"
        ),

        "buy_ok": "🎉  <b>支付成功！</b>\n\n<code>{delivery}</code>\n\n{delivery_note}<i>查看下方附件</i>",
        "order_file_title": "订单",
        "order_file_delivery": "交付信息：",
        "delivery_more": "<i>显示 {shown}/{total} — 完整列表见附件</i>",
        "buy_not_enough": "⚠️  <b>余额不足</b>\n\n/topup 充值",

        "topup_choose_method": "💳  <b>充值</b>\n\n<i>选择支付方式</i>",
        "topup_ask_amount": "<b>输入金额</b>\n\n<i>例如: 5, 10, 50</i>",
        "topup_invoice": "📋  <b>充值发票</b>\n\n  网络    <b>{network}</b>\n  币种    <b>{coin}</b>\n  金额    <b>{amount}</b>\n\n地址:\n<code>{address}</code>\n\n⚠️  仅通过正确网络/币种发送\n<i>Bot自动确认</i>",
        "topup_exchange_fee_warning": "⚠️  <b>手续费通知</b>\n\n请额外支付手续费。\n充值 <b>{amount} USD</b> → 发送 <b>{amount} + 手续费</b>",
        "topup_success": "🎉  <b>充值成功！</b>\n\n余额已更新\nID: <code>{topup_id}</code>",
        "topup_pending": "⏳  <b>等待支付</b>\n\nID: <code>{topup_id}</code>\n有效期: 30分钟\n\n<i>Bot将自动通知</i>",
        "topup_pending_exists": "⚠️  <b>已有待处理充值</b>\n\nID: <code>{topup_id}</code>\n过期: {expire_time}\n\n<b>Cancel</b> 取消并重新创建",
        "topup_cancelled": "✅  已取消。可以重新 /topup",
        "topup_failed": "❌  <b>充值失败/已过期</b>\nID: <code>{topup_id}</code>",

        "topup_binance_pay_invoice": (
            "🟠  <b>Binance ID Pay (P2P)</b>\n\n"
            "从Binance App发送USDT:\n\n"
            "  Binance ID\n  <code>{binance_id}</code>\n\n"
            "  备注 <i>(必填)</i>\n  <code>{note}</code>\n\n"
            "  金额: <b>{amount} USDT</b>\n\n"
            "⚠️  <b>必须填写备注</b>\n\n"
            "<i>发送后约30秒自动到账</i>"
        ),

        "me": "👤  <b>个人资料</b>\n- ID: <code>{tid}</code>\n- @{username}\n- 语言: <b>{user_lang}</b>",
        "me_format": "👤  <b>您的账户</b>\n\n  ID             <code>{tid}</code>\n  用户名    @{username}\n  语言        {user_lang}\n\n  💰  余额  <b>{balance} {currency}</b>\n\n<i>/topup 充值  ·  /menu 购物</i>",
        "history_title": "📜  <b>历史</b>\n{items}",
        "history_choose_month": "📅  <b>订单历史</b>\n\n<i>选择月份</i>",
        "history_list_title": "📅  <b>订单 {month}/{year}</b>\n\n总计: {total}\n\n<i>选择订单</i>",
        "history_no_orders": "本月没有订单。",
        "history_order_detail": "📦  <b>订单详情</b>\n\n  代码        <code>{order_code}</code>\n  商品        {product_name}\n  数量        {qty}\n  单价        {unit_price} {currency}\n\n  小计        {subtotal} {currency}\n  折扣       -{discount_total} {currency}\n  优惠券   {coupon_code}\n  ─────────────\n  <b>总计        {total} {currency}</b>\n\n  状态        <b>{status}</b>\n  创建        {created_at}",
        "ticket_ask": "描述问题并可附加照片。",
        "ticket_ok": "✅  工单: <code>{ticket_id}</code>",
        "error_no_orders": "没有可保修的订单。",
        "error_select_order_title": "🛡  <b>保修</b>\n\n总计: {total}\n\n<i>选择订单</i>",
        "error_ask_reason": "📦  <b>订单信息</b>\n\n  代码    <code>{order_code}</code>\n  商品    {product_name}\n  数量    {qty}\n  总计    {total} {currency}",
        "error_enter_reason": "<b>输入保修原因</b>\n\n<i>例如: 商品有缺陷、不工作...</i>",
        "error_enter_reason_with_photo": "<b>输入保修原因</b>\n\n可以附加照片\n<i>例如: 商品有缺陷、不工作...</i>",
        "error_photo_saved": "📸  照片已保存。请输入原因:",
        "error_reason_empty": "原因不能为空。",
        "error_confirm_with_reason": "🛡  <b>确认保修</b>\n\n  代码    <code>{order_code}</code>\n  商品    {product_name}\n  数量  {qty}  ·  总计  {total} {currency}\n\n  <b>原因:</b>\n  {reason}\n\n<i>点击</i> ✅",
        "error_ticket_created": "✅  <b>保修已提交</b>\n\nTicket: <code>{ticket_id}</code>\n\n<i>/tickets 跟踪状态</i>",
        "error_ticket_created_short": "✅  保修已提交",
        "error_cancelled": "保修请求已取消。",
        "cancelled": "已取消",
        "tickets_title": "🎫  <b>保修工单</b>\n\n总计: {total}\n\n<i>选择工单</i>",
        "tickets_empty": "没有保修工单。\n\n<i>/warranty 创建</i>",
        "tickets_detail": "🎫  <b>工单详情</b>\n\n  工单      <code>{ticket_id}</code>\n  订单      <code>{order_code}</code>\n  状态      <b>{status}</b>\n\n  <b>内容:</b>\n  {text}\n\n  创建    {created_at}{replacement_info}",
        "tickets_replacement": "\n\n🎁  <b>替换物品:</b>\n<code>{items}</code>",
        "buy_file_caption": "订单 {order_code}",
        "lang_choose": "🌐  <b>语言</b>\n\n<i>选择显示语言</i>",
        "generic_error": "出错了，请重试。",
        "user_banned": "账户已被封禁。联系管理员。",
        "none_coupon": "无",
        "flood_warning": "消息太频繁 — 等2-3秒。",
        "spam_blocked": "因垃圾消息被封禁 {minutes} 分钟。",
        "btn_products": "🛍 商店",
        "btn_balance": "💰 余额",
        "btn_refresh": "🔄 刷新",
        "btn_payment": "💳 充值",
        "btn_help": "📖 帮助",
        "placeholder_quick_buttons": "点击按钮或输入命令...",
        "welcome_title": "🛍  <b>欢迎来到商店</b>",
        "welcome_features": "✦  浏览和购买\n✦  加密充值\n✦  订单历史\n✦  快速保修",
        "welcome_commands": "<b>命令:</b>\n\n  /menu  ·  商店\n  /topup  ·  充值\n  /me  ·  账户\n  /history  ·  历史\n  /tickets  ·  工单\n  /warranty  ·  保修\n  /lang  ·  语言",
        "welcome_tip": "<i>使用下方快捷按钮</i>",
        "out_of_stock_detail": "⚠️  <b>库存不足</b>\n\n选择了: {qty} 件{stock_info}\n\n<i>减少数量或 /menu</i>",
        "product_not_found": "商品未找到。",
        "insufficient_balance": "⚠️  <b>余额不足</b>\n\n  余额    {balance} USD\n  需要    {total} USD\n\n<i>/topup 充值</i>",
        "invalid_data": "数据无效。",
        "server_error": "服务器错误。请稍后重试。",
        "cancel_flow": "操作已取消。",
        "buy_cancelled": "交易已取消。/menu",
        "payment_check": "💳  <b>检查支付</b>\n\n  /topup  ·  待处理\n  /history  ·  交易历史",
        "buy_success_short": "✅  购买成功！",
        "lang_changed": "✅  已切换: {lang}",
        "keyboard_updated": "键盘已更新。",
    },
}
