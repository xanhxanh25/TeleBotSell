# Chạy bằng Docker (thay cho start_all)

Mục tiêu của cấu hình này:
- Chạy `APITELE`, `token_shop_backend`, `AdminWeb` bằng Docker.
- **Không tạo database mới**, không có service Postgres trong compose.
- `TokenPay` chạy Docker riêng của bạn, khởi động sau.

## 1) Chuẩn bị biến môi trường

### `token_shop_backend/.env`
File này phải tồn tại và trỏ vào **DB hiện có**.

Lưu ý quan trọng khi chạy trong container:
- Nếu database chạy trên máy host Windows, host trong `DATABASE_URL` nên là `host.docker.internal` (không dùng `127.0.0.1`).

Ví dụ:
`DATABASE_URL=postgresql+psycopg2://postgres:postgres@host.docker.internal:5432/tele_shop`

### `APITELE/.env`
Giữ các biến hiện tại. Trong docker compose đã override các biến kết nối nội bộ:
- `ORDER_API_BASE=http://backend:8000`
- `ADMIN_API_BASE=http://adminweb:8001`
- `PAYMENT_API_BASE=http://host.docker.internal:5001`

## 2) Chạy services

Từ thư mục gốc project:

```powershell
docker compose up -d --build
```

Services được chạy:
- Backend: `http://localhost:8000`
- AdminWeb: `http://localhost:8001`
- APITELE: chạy bot (không public port)

## 3) Mở TokenPay riêng

Bạn tự chạy stack Docker của `TokenPay` sau (như bạn yêu cầu).

Compose này đã cấu hình backend + apitele gọi tokenpay qua:
- `http://host.docker.internal:5001`

## 4) Kiểm tra nhanh

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f adminweb
docker compose logs -f apitele
```

## 5) Dừng services

```powershell
docker compose down
```
