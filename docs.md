# TeleShop - Tài liệu kỹ thuật

Tài liệu này chứa phần chi tiết được tách khỏi README: biến môi trường, cách chạy Docker, nhóm API, database/migration và vận hành.

## Biến môi trường chính

| Biến | Mô tả |
| --- | --- |
| `DATABASE_URL` | Kết nối PostgreSQL. Trong Compose dùng `postgresql+psycopg2://postgres:postgres@postgres:5432/tele_shop`. |
| `BOT_TOKEN` | Token Telegram bot. |
| `BOT_API_KEY` | Key backend dùng để xác thực bot. |
| `BACKEND_BOT_API_KEY` | Key APITELE gửi qua header `X-Bot-Api-Key`, nên trùng `BOT_API_KEY`. |
| `ADMIN_API_KEY` | Key gọi Admin API qua header `X-Admin-Key`. |
| `TOKENPAY_API_BASE` | URL TokenPay, trong Compose là `http://tokenpay:5001`. |
| `TOKENPAY_API_TOKEN` | Token backend dùng khi gọi TokenPay, phải khớp `ApiToken` trong `appsettings.json`. |
| `PUBLIC_BASE_URL` | URL TokenPay gọi webhook về backend. Trong Compose là `http://token_shop_backend:8000`. |
| `ORDER_API_BASE` | URL backend order API cho APITELE. |
| `PAYMENT_API_BASE` | URL backend payment/topup API cho APITELE. |
| `ADMIN_API_BASE` | URL AdminWeb cho APITELE. |
| `ADMIN_USERNAME` | Tên đăng nhập AdminWeb, mặc định `admin`. |
| `ADMIN_PASSWORD_HASH` | Bcrypt hash mật khẩu AdminWeb. |
| `ADMIN_SECRET_KEY` | Secret ký session AdminWeb. |
| `ADMIN_TOTP_SECRET` | Secret 2FA TOTP, để trống nếu chưa bật 2FA. |

## Chạy Docker

```bash
cp .env.example .env
docker compose up -d --build
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

Dừng:

```bash
docker compose down
```

Production override không expose port host:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## API backend

Backend chạy ở `token_shop_backend:8000`. Khi expose local:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### Public

Không yêu cầu key:

- `GET /health`
- `GET /public/products`
- `GET /public/products/{product_id}`

### Bot/User

Yêu cầu header:

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

### Topup/Payment

- `POST /topups/create`
- `GET /topups/{topup_id}`
- `POST /topups/{topup_id}/cancel`
- `POST /pay/tokenpay/notify_url`
- `GET /pay/tokenpay/return_url`

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

Prefix: `/seller/v1`. Seller API dùng HMAC auth.

- `GET /seller/v1/products`
- `GET /seller/v1/products/{product_id}`
- `POST /seller/v1/checkout`
- `GET /seller/v1/balance`
- `GET /seller/v1/orders`
- `POST /seller/v1/coupons`
- `GET /seller/v1/coupons`
- `DELETE /seller/v1/coupons/{coupon_id}`

## Database và migration

Backend dùng SQLAlchemy models trong `token_shop_backend/app/models`.

Khi startup, backend gọi:

```python
Base.metadata.create_all(bind=engine)
```

Các migration thủ công còn được giữ trong:

```text
token_shop_backend/migrations/
```

Không xóa thư mục này nếu còn cần dựng database mới hoặc nâng schema.

## Ghi chú dọn dẹp

Các file log, cache, test, build artifact, backup, `.sh`, DB mẫu và script phụ trợ đã được xóa khỏi workspace. Những file migration trong `token_shop_backend/migrations` được giữ lại vì vẫn có thể cần cho database.
