# TeleShop - Telegram Token Shop

TeleShop là hệ thống bán hàng số qua Telegram. Người dùng tương tác với bot để xem sản phẩm, mua hàng, nạp tiền, tra lịch sử và gửi ticket bảo hành/báo lỗi. Admin quản lý toàn bộ shop qua web riêng: sản phẩm, kho, coupon, user, đơn hàng, topup, ticket, broadcast và seller API key.

Hệ thống được đóng gói bằng Docker Compose, gồm backend FastAPI, bot Telegram aiogram, AdminWeb FastAPI/Jinja, PostgreSQL và TokenPay .NET 8.

## Ứng dụng này làm gì?

- Bán sản phẩm số qua Telegram: user chọn sản phẩm, nhập số lượng, áp coupon nếu có và checkout bằng số dư.
- Nạp tiền tự động: backend tạo topup, TokenPay xử lý thanh toán và gọi webhook về backend khi nhận tiền.
- Giao hàng tự động: sản phẩm dùng stock item, sau khi mua thành công hệ thống trả payload/hàng cho user.
- Quản trị shop: admin tạo/sửa sản phẩm, import stock, quản lý coupon, user, balance, đơn hàng, topup và ticket.
- Hỗ trợ sau bán: user gửi ticket bảo hành/báo lỗi, admin duyệt/reject và có thể gửi replacement qua Telegram.
- Mở API cho seller: admin cấp seller API key, seller gọi API HMAC để xem sản phẩm, checkout, xem balance/orders và tạo coupon.
<img width="647" height="339" alt="Screenshot 2026-05-18 180815" src="https://github.com/user-attachments/assets/a7149336-5b0f-41dd-9b01-37273b5e95eb" />

## Minh chứng từ source

Các chức năng trên đang được thể hiện trực tiếp trong source:

- `docker-compose.yml` định nghĩa đủ 5 service: `postgres`, `tokenpay`, `token_shop_backend`, `adminweb`, `apitele`.
- `token_shop_backend/app/main.py` khởi tạo FastAPI, middleware bảo mật/logging, router public/order/topup/admin/user/ticket/seller và background cleanup.
- `token_shop_backend/app/api/tokenpay_webhooks.py` nhận webhook `/pay/tokenpay/notify_url` từ TokenPay.
- `token_shop_backend/app/routers/seller_api.py` cung cấp seller API prefix `/seller/v1` với HMAC auth.
- `APITELE/app/main.py` khởi tạo bot aiogram polling, đăng ký command, middleware rate limit/anti-flood và client gọi backend.
- `AdminWeb/main.py` cung cấp dashboard, quản lý product/stock/coupon/user/order/topup/ticket/broadcast/seller key.
- `TokenPay/src/TokenPay/BgServices/` chứa các background service kiểm tra thanh toán, hết hạn order, notify và update rate.
- `token_shop_backend/tests/` có test cho coupon, bậc giá theo số lượng, seller API và security.

## Kiến trúc tổng quan

```text
User Telegram
    |
    v
APITELE bot (aiogram, polling)
    | X-Bot-Api-Key
    v
token_shop_backend (FastAPI, port 8000)
    | SQLAlchemy
    v
PostgreSQL (tele_shop)

Admin browser
    |
    v
AdminWeb (FastAPI/Jinja, port 8001)
    |
    +--> PostgreSQL
    +--> Telegram Bot API để broadcast/gửi file

Backend
    |
    v
TokenPay (.NET 8, port 5001)
    |
    +--> TokenPay SQLite volume
    +--> Blockchain/Binance providers
    +--> POST /pay/tokenpay/notify_url về backend
```

Trong Docker Compose, các service gọi nhau bằng tên service nội bộ:

- `apitele` gọi `http://token_shop_backend:8000` và `http://adminweb:8001`.
- `token_shop_backend` gọi `http://tokenpay:5001`.
- `tokenpay` gọi webhook về `PUBLIC_BASE_URL`, mặc định là `http://token_shop_backend:8000`.
- `token_shop_backend` và `adminweb` kết nối PostgreSQL qua `postgres:5432`.

## Thành phần chính

| Thành phần | Công nghệ | Vai trò |
| --- | --- | --- |
| `token_shop_backend` | FastAPI, SQLAlchemy | API nghiệp vụ, order, topup, coupon, ticket, seller API, webhook TokenPay |
| `APITELE` | aiogram | Bot Telegram cho người dùng cuối |
| `AdminWeb` | FastAPI, Jinja2 | Giao diện quản trị shop |
| `TokenPay` | ASP.NET Core .NET 8 | Cổng thanh toán và kiểm tra giao dịch |
| `postgres` | PostgreSQL 16 | Database chính của shop |

## Luồng nghiệp vụ chính

### Mua hàng

1. User mở bot Telegram và dùng `/menu` để xem danh sách sản phẩm.
2. Bot gọi backend lấy sản phẩm còn active/còn stock.
3. User chọn sản phẩm, nhập số lượng và có thể nhập coupon.
4. Bot gọi backend quote giá, sau đó checkout.
5. Backend kiểm tra balance, coupon, tồn kho và tạo order.
6. Nếu thành công, backend trừ số dư, commit stock item và trả hàng về bot.

### Nạp tiền

1. User dùng `/topup` và nhập số tiền cần nạp.
2. Backend tạo topup pending và gọi TokenPay tạo invoice.
3. Bot gửi thông tin thanh toán/QR/link cho user.
4. TokenPay kiểm tra giao dịch nền.
5. Khi nhận tiền, TokenPay gọi webhook về backend.
6. Backend cập nhật topup, cộng balance và bot polling trạng thái để báo kết quả cho user.
<img width="861" height="1091" alt="Screenshot 2026-05-18 180824" src="https://github.com/user-attachments/assets/c7d98743-f933-457f-a9d8-876d64bac037" />

### Bảo hành/báo lỗi

1. User dùng `/warranty` hoặc `/error`.
2. Bot gửi ticket về backend.
3. Admin xem ticket trong AdminWeb.
4. Admin approve/reject, có thể gửi replacement item/file qua Telegram.

### Seller API

1. Admin tạo API key/secret cho seller trong AdminWeb.
2. Seller ký request bằng HMAC.
3. Seller gọi API để xem sản phẩm, checkout, xem balance/orders hoặc tạo coupon cho user.

## Cấu trúc thư mục

```text
.
|-- docker-compose.yml              # Stack Docker đầy đủ
|-- docker-compose.prod.yml         # Override production, đóng port host
|-- .env.example                    # Mẫu biến môi trường chính
|-- DEPLOY_DOCKER.md                # Deploy, backup/restore, migration
|-- docs.md                         # Tài liệu kỹ thuật chi tiết
|-- AdminWeb/
|   |-- main.py                     # Admin web FastAPI/Jinja
|   |-- templates/                  # Dashboard, product, user, order, topup, ticket...
|   `-- Dockerfile
|-- APITELE/
|   |-- run.py                      # Entrypoint bot
|   |-- app/main.py                 # Khởi tạo aiogram bot/dispatcher
|   |-- app/handlers/               # /start, /menu, /topup, /history, /tickets...
|   |-- app/services/               # HTTP client gọi backend/admin/payment
|   `-- Dockerfile
|-- token_shop_backend/
|   |-- app/main.py                 # FastAPI app chính
|   |-- app/api/                    # Public, order, topup, admin, user, ticket, webhook
|   |-- app/routers/seller_api.py   # Seller API HMAC
|   |-- app/models/                 # SQLAlchemy models
|   |-- app/services/               # Business logic
|   |-- migrations/                 # Migration script thủ công
|   |-- tests/                      # Unit/API/concurrency tests
|   `-- Dockerfile
`-- TokenPay/
    `-- src/
        |-- Dockerfile              # Build .NET 8
        `-- TokenPay/
            |-- Controllers/
            |-- BgServices/
            |-- Domains/
            `-- appsettings.json
```

## API demo

README chỉ để một vài endpoint tiêu biểu để hình dung hệ thống. Danh sách API đầy đủ nằm trong [docs.md](docs.md).

### Public

```http
GET /health
GET /public/products
GET /public/products/{product_id}
```

### Bot mua hàng

Bot gọi backend với header:

```http
X-Bot-Api-Key: <BOT_API_KEY>
```

Ví dụ:

```http
POST /orders/quote
POST /orders/checkout
GET /orders/history?telegram_id=123456
```

### Nạp tiền và webhook TokenPay

```http
POST /topups/create
GET /topups/{topup_id}
POST /pay/tokenpay/notify_url
```

### Admin

Admin API dùng header:

```http
X-Admin-Key: <ADMIN_API_KEY>
```

Ví dụ:

```http
POST /admin/products
POST /admin/topups/approve
GET /admin/tickets
```

### Seller API

Seller API dùng prefix `/seller/v1` và HMAC auth:

```http
GET /seller/v1/products
POST /seller/v1/checkout
GET /seller/v1/balance
```

## Chạy nhanh bằng Docker

Tạo file môi trường:

```bash
cp .env.example .env
```

Trên PowerShell:

```powershell
Copy-Item .env.example .env
```

Sửa các giá trị quan trọng trong `.env`:

- `BOT_TOKEN`
- `ADMIN_API_KEY`
- `BOT_API_KEY`
- `BACKEND_BOT_API_KEY`
- `TOKENPAY_API_TOKEN`
- `ADMIN_SECRET_KEY`
- `ADMIN_PASSWORD_HASH`
- `PUBLIC_BASE_URL`

Đồng bộ `TokenPay/src/TokenPay/appsettings.json`: `ApiToken` phải khớp với `TOKENPAY_API_TOKEN`.

Khởi động:

```bash
docker compose up -d --build
```

Kiểm tra:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8001/health
```

URL mặc định:

| URL | Mô tả |
| --- | --- |
| `http://127.0.0.1:8000/docs` | Swagger UI backend |
| `http://127.0.0.1:8000/redoc` | ReDoc backend |
| `http://127.0.0.1:8001/` | AdminWeb |
| `http://127.0.0.1:5001/` | TokenPay |

## Tài liệu chi tiết

- [docs.md](docs.md): biến môi trường, cách chạy, API groups đầy đủ, test, database/migration, quy trình vận hành.
- [DEPLOY_DOCKER.md](DEPLOY_DOCKER.md): hướng dẫn deploy Docker, backup/restore và migration.
- [README_DOCKER.md](README_DOCKER.md): ghi chú Docker ngắn.
- [APITELE/README_RUN.md](APITELE/README_RUN.md): hướng dẫn chạy bot.
- [AdminWeb/README_RUN.md](AdminWeb/README_RUN.md): hướng dẫn AdminWeb.
- [token_shop_backend/README.md](token_shop_backend/README.md): ghi chú backend API có sẵn.
