# TeleShop - Telegram Token Shop

Hệ thống bán hàng số qua Telegram, gồm bot người dùng, backend API, trang quản trị, PostgreSQL và cổng thanh toán TokenPay. Dự án được đóng gói bằng Docker Compose để có thể chạy đầy đủ các thành phần trên cùng một host.

Chức năng chính:

- Bot Telegram cho người dùng xem sản phẩm, mua hàng, nạp tiền, xem lịch sử, đổi ngôn ngữ và gửi ticket bảo hành/báo lỗi.
- Backend FastAPI xử lý sản phẩm, đơn hàng, nạp tiền, coupon, ticket, user, seller API và webhook TokenPay.
- AdminWeb FastAPI + Jinja cho quản trị sản phẩm, kho, user, coupon, đơn hàng, topup, ticket, broadcast và seller API key.
- TokenPay .NET 8 xử lý tạo đơn thanh toán crypto/fiat, theo dõi giao dịch và gọi notify webhook về backend.
- PostgreSQL lưu dữ liệu nghiệp vụ của shop; TokenPay dùng SQLite riêng trong Docker volume.

## Mục Lục

1. [Kiến trúc tổng quan](#kiến-trúc-tổng-quan)
2. [Cấu trúc thư mục](#cấu-trúc-thư-mục)
3. [Điều kiện môi trường](#điều-kiện-môi-trường)
4. [Cài đặt bằng Docker](#cài-đặt-bằng-docker)
5. [Biến môi trường](#biến-môi-trường)
6. [Chạy hệ thống](#chạy-hệ-thống)
7. [Các nhóm API](#các-nhóm-api)
8. [AdminWeb](#adminweb)
9. [Telegram Bot](#telegram-bot)
10. [TokenPay](#tokenpay)
11. [Database và migration](#database-và-migration)
12. [Test](#test)
13. [Quy trình làm việc](#quy-trình-làm-việc)
14. [Vận hành và bảo mật](#vận-hành-và-bảo-mật)
15. [Tài liệu liên quan](#tài-liệu-liên-quan)

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

Trong Docker Compose, các service nội bộ gọi nhau bằng tên service:

- `apitele` gọi `http://token_shop_backend:8000` và `http://adminweb:8001`.
- `token_shop_backend` gọi `http://tokenpay:5001`.
- `tokenpay` gọi webhook về `PUBLIC_BASE_URL`, mặc định là `http://token_shop_backend:8000`.
- `token_shop_backend` và `adminweb` kết nối PostgreSQL qua `postgres:5432`.

## Cấu trúc thư mục

```text
.
|-- docker-compose.yml              # Stack Docker dev/server
|-- docker-compose.prod.yml         # Override production: không expose port ra host
|-- .env.example                    # Mẫu biến môi trường dùng chung
|-- .env.docker.example             # Mẫu env cũ/bổ sung cho Docker
|-- DEPLOY_DOCKER.md                # Ghi chú deploy Docker chi tiết
|-- README_DOCKER.md                # Hướng dẫn Docker ngắn
|-- start_all.sh / stop_all.sh      # Script chạy/dừng theo kiểu server cũ
|-- AdminWeb/
|   |-- main.py                     # Admin web FastAPI/Jinja
|   |-- Dockerfile
|   |-- requirements.txt
|   |-- templates/                  # Giao diện admin
|   `-- static/
|-- APITELE/
|   |-- run.py                      # Entrypoint bot
|   |-- app/main.py                 # Khởi tạo aiogram Dispatcher/Bot
|   |-- app/handlers/               # /start, /menu, /topup, /history, /tickets...
|   |-- app/services/               # Client gọi backend/admin/payment
|   |-- app/middlewares/            # Rate limit, anti-flood, network error
|   |-- app/i18n/                   # Đa ngôn ngữ
|   |-- Dockerfile
|   `-- requirements.txt
|-- token_shop_backend/
|   |-- app/main.py                 # FastAPI app chính
|   |-- app/api/                    # Public/order/topup/admin/user/ticket/webhook API
|   |-- app/routers/seller_api.py   # Seller API HMAC
|   |-- app/models/                 # SQLAlchemy models
|   |-- app/schemas/                # Pydantic schemas
|   |-- app/services/               # Business logic
|   |-- app/middleware(s)/          # Firewall, logging, sanitizer, timing
|   |-- migrations/                 # Migration script SQL/Python thủ công
|   |-- tests/                      # Unit/API/concurrency tests
|   |-- Dockerfile
|   `-- requirements*.txt
`-- TokenPay/
    `-- src/
        |-- Dockerfile              # Multi-stage .NET 8 build
        `-- TokenPay/
            |-- Program.cs
            |-- Controllers/
            |-- BgServices/
            |-- Domains/
            |-- appsettings.json
            `-- appsettings.Example.json
```

Bỏ qua khi đọc source: `__pycache__/`, `bin/`, `obj/`, `logs/`, file backup, database tạm và các file sinh từ build/runtime.

## Điều kiện môi trường

Cần có:

- Docker Engine và Docker Compose plugin.
- Telegram bot token từ BotFather.
- Cấu hình TokenPay hợp lệ: API token, địa chỉ ví, provider blockchain/Binance nếu dùng.
- Nếu deploy production qua domain: reverse proxy HTTPS trỏ tới backend/admin/tokenpay theo nhu cầu.

Kiểm tra Docker:

```bash
docker --version
docker compose version
```

## Cài đặt bằng Docker

1. Tạo file môi trường:

```bash
cp .env.example .env
```

Trên PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Sửa `.env`, tối thiểu cần thay:

- `BOT_TOKEN`
- `ADMIN_API_KEY`
- `BOT_API_KEY`
- `BACKEND_BOT_API_KEY`
- `TOKENPAY_API_TOKEN`
- `ADMIN_SECRET_KEY`
- `ADMIN_PASSWORD_HASH`
- `PUBLIC_BASE_URL`

3. Sửa `TokenPay/src/TokenPay/appsettings.json`:

- `ApiToken` phải khớp với `TOKENPAY_API_TOKEN`.
- `ConnectionStrings:DB` nên giữ `Data Source=/data/TokenPay.db;` để database TokenPay nằm trong Docker volume.
- Thay các khóa, địa chỉ ví, token và provider thật của môi trường production.

4. Build và chạy:

```bash
docker compose up -d --build
```

## Biến môi trường

Biến chính trong `.env`:

| Biến | Dùng cho | Mô tả |
| --- | --- | --- |
| `ENV` | tất cả | Môi trường chạy, ví dụ `prod`. |
| `DATABASE_URL` | backend, admin | Chuỗi kết nối PostgreSQL. Trong Compose nên dùng `postgresql+psycopg2://postgres:postgres@postgres:5432/tele_shop`. |
| `ADMIN_API_KEY` | backend/admin scripts | Key gọi các endpoint `/admin/*`, gửi qua header `X-Admin-Key`. |
| `BOT_API_KEY` | backend | Key backend dùng để xác thực bot. |
| `BACKEND_BOT_API_KEY` | APITELE | Key bot gửi tới backend qua header `X-Bot-Api-Key`; nên trùng `BOT_API_KEY`. |
| `TOKENPAY_API_BASE` | backend | Base URL TokenPay. Trong Compose: `http://tokenpay:5001`. |
| `TOKENPAY_API_TOKEN` | backend, TokenPay | Token xác thực khi backend gọi TokenPay; phải khớp `ApiToken` trong `appsettings.json`. |
| `PUBLIC_BASE_URL` | backend/TokenPay flow | URL TokenPay có thể gọi về backend. Trong Compose: `http://token_shop_backend:8000`; production có thể là domain HTTPS. |
| `BOT_TOKEN` | APITELE, AdminWeb broadcast | Token Telegram bot. |
| `ORDER_API_BASE` | APITELE | Backend order API, trong Compose: `http://token_shop_backend:8000`. |
| `PAYMENT_API_BASE` | APITELE | Backend topup/payment API, trong Compose: `http://token_shop_backend:8000`. |
| `ADMIN_API_BASE` | APITELE | AdminWeb API/base, trong Compose: `http://adminweb:8001`. |
| `HTTP_TIMEOUT_SEC`, `HTTP_RETRIES` | APITELE | Timeout/retry khi bot gọi HTTP API. |
| `ADMIN_USERNAME` | AdminWeb | Tên đăng nhập admin, mặc định `admin` nếu không set. |
| `ADMIN_PASSWORD_HASH` | AdminWeb | Bcrypt hash mật khẩu admin. |
| `ADMIN_SECRET_KEY` | AdminWeb | Secret ký session cookie. |
| `ADMIN_TOTP_SECRET` | AdminWeb | Secret 2FA TOTP; để trống nếu chưa bật 2FA. |
| `ADMIN_SESSION_MAX_AGE` | AdminWeb | Thời gian sống session, mặc định 30 ngày. |
| `ADMIN_HTTPS_ONLY` | AdminWeb | Đặt `true` khi chạy sau HTTPS để cookie chỉ gửi qua HTTPS. |

Một số biến backend bổ sung:

- `RETENTION_DAYS`: số ngày giữ bản ghi cũ trước khi cleanup.
- `TOKENPAY_EXPIRE_TZ`: timezone hiển thị hết hạn topup, mặc định `Asia/Ho_Chi_Minh`.
- `BINANCE_NOTE_PREFIX`: tiền tố nội dung chuyển khoản Binance, mặc định `SHOP`.
- `DEBUG_TOPUP_TIME`: bật log/debug thời gian topup khi đặt `1`.

Không commit `.env` hoặc `appsettings.json` có secret thật lên repository.

## Chạy hệ thống

Khởi động full stack:

```bash
docker compose up -d --build
```

Xem trạng thái:

```bash
docker compose ps
```

Xem log:

```bash
docker compose logs -f token_shop_backend
docker compose logs -f adminweb
docker compose logs -f apitele
docker compose logs -f tokenpay
docker compose logs -f postgres
```

Dừng hệ thống:

```bash
docker compose down
```

Khởi động lại một service:

```bash
docker compose restart apitele
docker compose restart token_shop_backend
```

Endpoint mặc định khi chạy `docker-compose.yml`:

| URL | Mô tả |
| --- | --- |
| `http://127.0.0.1:8000/health` | Backend health check |
| `http://127.0.0.1:8000/docs` | Swagger UI backend |
| `http://127.0.0.1:8000/redoc` | ReDoc backend |
| `http://127.0.0.1:8001/health` | AdminWeb health check |
| `http://127.0.0.1:8001/` | AdminWeb |
| `http://127.0.0.1:5001/` | TokenPay |

Production override không expose port ra host:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Khi dùng override này, nên đặt reverse proxy cùng Docker network hoặc sửa lại expose/ports theo kiến trúc deploy.

## Các nhóm API

Backend FastAPI chạy ở service `token_shop_backend`, port nội bộ `8000`.

### Public API

Không yêu cầu key:

- `GET /health`
- `GET /public/products`
- `GET /public/products/{product_id}`

### Bot/User API

Dùng cho APITELE. Các route này yêu cầu header:

```http
X-Bot-Api-Key: <BOT_API_KEY>
```

Endpoints:

- `POST /orders/quote`
- `POST /orders/checkout`
- `GET /orders/history?telegram_id=...`
- `GET /orders/{order_id}`
- `GET /users/me?telegram_id=...`
- `POST /tickets`
- `GET /tickets`
- `GET /tickets/{ticket_id}`

### Topup/Payment API

- `POST /topups/create`
- `GET /topups/{topup_id}`
- `POST /topups/{topup_id}/cancel`
- `POST /pay/tokenpay/notify_url`
- `GET /pay/tokenpay/return_url`

`/pay/tokenpay/notify_url` là webhook TokenPay gọi về backend sau khi phát hiện thanh toán.

### Admin API

Yêu cầu header:

```http
X-Admin-Key: <ADMIN_API_KEY>
```

Endpoints chính:

- `GET /admin/users/{telegram_id}/balance`
- `POST /admin/products`
- `POST /admin/coupons`
- `POST /admin/coupons/{coupon_id}/add-uses`
- `GET /admin/coupons/{coupon_id}/redemptions`
- `POST /admin/topups/approve`
- `POST /admin/products/{product_id}/stock-items/import`
- `GET /admin/products/{product_id}/stock-items`
- `GET /admin/products/{product_id}/stock-items/download`
- `DELETE /admin/products/{product_id}/stock-items/by-id/{item_id}`
- `DELETE /admin/products/{product_id}/stock-items/bulk`
- `DELETE /admin/products/{product_id}/stock-items/all`
- `POST /admin/products/{product_id}/sync-stock`
- `POST /admin/products/sync-stock-all`
- `POST /admin/tickets/{ticket_id}/approve`
- `GET /admin/tickets`
- `POST /admin/orders/{order_id}/reverse_coupon_usage`

### Seller API

Prefix: `/seller/v1`.

Seller API dùng HMAC-SHA256 qua middleware `verify_seller_hmac`. API key/secret được tạo trong AdminWeb tại mục seller.

Endpoints:

- `GET /seller/v1/products`
- `GET /seller/v1/products/{product_id}`
- `POST /seller/v1/checkout`
- `GET /seller/v1/balance`
- `GET /seller/v1/orders`
- `POST /seller/v1/coupons`
- `GET /seller/v1/coupons`
- `DELETE /seller/v1/coupons/{coupon_id}`

Tài liệu seller có sẵn trong AdminWeb:

- `/sellers/api-doc`
- `/sellers/api-doc/download`
- `/sellers/sdk-download`

## AdminWeb

AdminWeb chạy ở port `8001`, dùng FastAPI, Jinja2 templates, session cookie và tùy chọn TOTP 2FA.

Màn hình/chức năng chính:

- Dashboard thống kê.
- Quản lý sản phẩm, giá, stock, bậc giảm giá theo số lượng.
- Import/download/xóa stock item.
- Quản lý coupon và lịch sử sử dụng coupon.
- Quản lý user, khóa/mở khóa user, điều chỉnh/reset balance.
- Xem đơn hàng, topup, ticket.
- Duyệt/reject ticket và gửi replacement qua Telegram.
- Broadcast message tới user.
- Tạo, rotate, revoke seller API key và tải SDK/tài liệu.

Đăng nhập:

- URL: `http://127.0.0.1:8001/login`
- Username mặc định nếu không set: `admin`
- Mật khẩu phụ thuộc `ADMIN_PASSWORD_HASH`.

Nên tạo hash riêng cho production, không dùng giá trị mẫu.

## Telegram Bot

APITELE là bot aiogram chạy polling, không cần expose port.

Lệnh được đăng ký:

- `/start`
- `/menu`
- `/topup`
- `/me`
- `/history`
- `/tickets`
- `/help`
- `/warranty`
- `/error`
- `/lang`

Bot có:

- Rate limit và anti-flood middleware.
- Network error middleware để giảm crash khi Telegram/API lỗi tạm thời.
- Keepalive tới Telegram/backend.
- Watchdog log sức khỏe runtime.
- Cache sản phẩm/balance.
- Đa ngôn ngữ trong `APITELE/app/i18n`.

## TokenPay

TokenPay là ứng dụng ASP.NET Core .NET 8, build từ `TokenPay/src/Dockerfile`, chạy port `5001`.

Thành phần chính:

- `Controllers/HomeController.cs`: tạo order, trang thanh toán, check địa chỉ/transaction.
- `BgServices/`: job kiểm tra thanh toán TRON/BSC/ETH/EVM/Binance, hết hạn order, notify order thành công, update rate và collection.
- `Domains/`: entity order/token/rate.
- `appsettings.json`: cấu hình TokenPay.

Cần đồng bộ:

- `.env` `TOKENPAY_API_TOKEN`
- `TokenPay/src/TokenPay/appsettings.json` `ApiToken`
- backend `TOKENPAY_API_BASE`
- backend `PUBLIC_BASE_URL`

## Database và migration

Backend dùng SQLAlchemy models trong `token_shop_backend/app/models`. Khi startup, `token_shop_backend/app/main.py` gọi:

```python
Base.metadata.create_all(bind=engine)
```

Nghĩa là bảng có thể được tạo tự động cho môi trường mới. Dự án hiện chưa có Alembic; migration đang ở dạng script SQL/Python thủ công trong:

```text
token_shop_backend/migrations/
token_shop_backend/migrate_*.py
token_shop_backend/migrate_*.sql
```

Một số migration đang có:

- `add_sort_order_to_products`
- `add_coupon_product_user_columns`
- `add_telegram_user_column`
- `add_product_qty_discount_tiers`
- `add_coupon_usage_limits`
- `add_coupon_redemptions`
- `create_seller_api_keys`

Backup/restore production nên làm trước khi chạy migration. Xem thêm `DEPLOY_DOCKER.md`.

## Test

Test backend nằm trong `token_shop_backend/tests`.

Chạy unit/API tests bằng Docker:

```bash
docker compose run --rm token_shop_backend sh -lc "pip install -r requirements-dev.txt && pytest -q"
```

Chạy riêng test seller/coupon:

```bash
docker compose run --rm token_shop_backend sh -lc "pip install -r requirements-dev.txt && pytest tests/test_coupon_service.py tests/test_seller_api.py tests/test_seller_security.py -q"
```

PostgreSQL concurrency test nằm trong `token_shop_backend/tests/pg` và cần database test riêng:

```bash
docker compose exec postgres createdb -U postgres coupon_test_db
docker compose run --rm -e COUPON_PG_TEST_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/coupon_test_db token_shop_backend sh -lc "pip install -r requirements-dev.txt && pytest tests/pg/ -q"
```

Nếu database đã tồn tại, lệnh `createdb` có thể báo lỗi; khi đó chỉ cần chạy lại pytest.

Kiểm tra health sau khi deploy:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:5001/
```

## Quy trình làm việc

Quy trình đề xuất khi phát triển:

1. Tạo branch/bản thay đổi riêng.
2. Cập nhật model/schema/service/router theo cùng một luồng nghiệp vụ.
3. Nếu đổi database, thêm migration idempotent vào `token_shop_backend/migrations`.
4. Cập nhật AdminWeb hoặc APITELE nếu API contract thay đổi.
5. Chạy test liên quan bằng Docker.
6. Chạy `docker compose up -d --build` và kiểm tra `/health`, `/docs`, AdminWeb, bot command.
7. Cập nhật README/tài liệu nếu thêm biến môi trường, API hoặc bước vận hành.

Quy trình deploy an toàn:

1. Backup PostgreSQL hiện tại.
2. Backup `TokenPay/src/TokenPay/appsettings.json` và volume TokenPay nếu đang dùng dữ liệu thật.
3. Cập nhật `.env` và image.
4. Build/start stack.
5. Chạy migration cần thiết.
6. Kiểm tra health, bot, topup thử nghiệm và admin login.
7. Theo dõi log `token_shop_backend`, `apitele`, `tokenpay` trong vài phút đầu.

## Vận hành và bảo mật

- Thay toàn bộ secret mẫu trước production: Telegram token, admin secret, API key, TokenPay token, provider key.
- Không expose PostgreSQL và TokenPay ra public nếu không có lý do. Mặc định compose bind PostgreSQL/backend/TokenPay về `127.0.0.1`; production override có thể đóng tất cả port.
- Dùng HTTPS/reverse proxy khi truy cập AdminWeb qua Internet; set `ADMIN_HTTPS_ONLY=true`.
- Bật `ADMIN_TOTP_SECRET` để có 2FA cho AdminWeb.
- Đồng bộ `BOT_API_KEY` và `BACKEND_BOT_API_KEY`, tránh để default `change_me`.
- Giới hạn quyền truy cập `appsettings.json` vì có thể chứa API key, địa chỉ ví và Telegram token.
- Theo dõi log lỗi webhook TokenPay và topup pending/expired.
- Sao lưu volume `postgres_data` và `tokenpay_data` định kỳ.
- Không commit file runtime: `.env`, `*.db`, logs, backup dump, QR code secret.

## Tài liệu liên quan

- `DEPLOY_DOCKER.md`: hướng dẫn deploy Docker, backup/restore và migration.
- `README_DOCKER.md`: ghi chú Docker ngắn.
- `README_UBUNTU.md`, `HUONG_DAN_CHAY_TREN_SERVER.md`: hướng dẫn server theo cách cũ.
- `AdminWeb/README_RUN.md`, `AdminWeb/README_UBUNTU.md`: hướng dẫn riêng cho AdminWeb.
- `APITELE/README_RUN.md`, `APITELE/README_BROADCAST.md`: hướng dẫn chạy bot và broadcast.
- `token_shop_backend/README.md`: ghi chú backend API có sẵn.
- `TokenPay/src/TokenPay/appsettings.Example.json`: mẫu cấu hình TokenPay.
