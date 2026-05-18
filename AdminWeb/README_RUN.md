# Hướng dẫn chạy AdminWeb

AdminWeb là ứng dụng quản lý (admin panel) cho hệ thống Telegram Shop, cung cấp giao diện web để quản lý sản phẩm, đơn hàng, người dùng, tickets, v.v.

## Yêu cầu

1. **Python 3.8+**
2. **Database PostgreSQL** (đã setup từ token_shop_backend)
3. **Dependencies** đã cài đặt
4. **File .env** từ token_shop_backend (chứa DATABASE_URL)

## Cấu hình

### 1. Database

AdminWeb sử dụng database từ `token_shop_backend`. Đảm bảo file `.env` trong `token_shop_backend/` có:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### 2. Environment Variables (Tùy chọn)

AdminWeb tự động load `.env` từ `token_shop_backend/.env`. Các biến môi trường tùy chọn:

- `ADMIN_SECRET_KEY`: Secret key cho session (mặc định: tự động generate)
- `ADMIN_PASSWORD_HASH`: SHA256 hash của password admin (mặc định: `cuocdoima@8386`)

**Mặc định:**
- Username: `linhlo`
- Password: `cuocdoima@8386`

## Cài đặt Dependencies

```bash
cd AdminWeb
pip install -r requirements.txt
```

Dependencies:
- fastapi==0.110.0
- uvicorn[standard]==0.29.0
- jinja2==3.1.4
- python-multipart==0.0.9
- sqlalchemy==2.0.25
- psycopg2-binary==2.9.9

## Cách chạy

### Cách 1: Chạy trực tiếp (Development)

```bash
cd AdminWeb
python main.py
```

Sẽ chạy với:
- Host: `0.0.0.0`
- Port: `8001`
- Reload: `True` (tự động reload khi code thay đổi)

Truy cập: http://localhost:8001

### Cách 2: Dùng Uvicorn (Production)

```bash
cd AdminWeb
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2
```

**Với workers (khuyến nghị cho production):**
- `--workers 2`: Chạy với 2 workers để xử lý nhiều requests đồng thời

### Cách 3: Dùng Service Manager (Khuyến nghị)

Từ thư mục gốc project:

```bash
# Chạy tất cả services (Backend, AdminWeb, APITELE)
python run_all_services.py start

# Hoặc chỉ chạy AdminWeb
python run_all_services.py adminweb start
```

Lợi ích:
- ✅ Quản lý tập trung
- ✅ Workers tự động (2 workers)
- ✅ Logging riêng
- ✅ Dễ dàng start/stop/restart

## Truy cập AdminWeb

1. Mở trình duyệt: http://localhost:8001
2. Đăng nhập với:
   - **Username**: `linhlo`
   - **Password**: `cuocdoima@8386`

## Đổi Password

### Cách 1: Dùng Python

```python
import hashlib
password = "your_new_password"
hash_password = hashlib.sha256(password.encode()).hexdigest()
print(hash_password)
```

### Cách 2: Thêm vào .env

Tạo file `.env` trong `AdminWeb/` (hoặc thêm vào `token_shop_backend/.env`):

```env
ADMIN_PASSWORD_HASH=<sha256_hash_của_password_mới>
```

## Các tính năng

- 📊 **Dashboard**: Tổng quan hệ thống
- 📦 **Products**: Quản lý sản phẩm
- 📝 **Orders**: Quản lý đơn hàng
- 💰 **Topups**: Quản lý nạp tiền
- 👥 **Users**: Quản lý người dùng
- 🎫 **Tickets**: Quản lý tickets/bảo hành
- 🎟️ **Coupons**: Quản lý mã giảm giá
- 📢 **Broadcast**: Gửi tin nhắn hàng loạt

## Port và URL

- **Port mặc định**: 8001
- **URL**: http://localhost:8001
- **Login URL**: http://localhost:8001/login

## Troubleshooting

### Lỗi: Database connection failed

**Nguyên nhân**: Không kết nối được database

**Giải pháp**:
1. Kiểm tra file `.env` trong `token_shop_backend/` có `DATABASE_URL` không
2. Kiểm tra PostgreSQL đang chạy
3. Kiểm tra thông tin kết nối (user, password, host, port, dbname)

### Lỗi: Port 8001 đã được sử dụng

**Giải pháp**:
```bash
# Windows: Tìm process đang dùng port 8001
netstat -ano | findstr :8001

# Kill process (thay <PID> bằng PID thực tế)
taskkill /PID <PID> /F

# Hoặc dùng port khác
uvicorn main:app --host 0.0.0.0 --port 8002
```

### Lỗi: Module not found

**Nguyên nhân**: Chưa cài đặt dependencies

**Giải pháp**:
```bash
cd AdminWeb
pip install -r requirements.txt
```

### Lỗi: Import token_shop_backend failed

**Nguyên nhân**: Cấu trúc thư mục không đúng

**Giải pháp**: Đảm bảo cấu trúc:
```
project_root/
├── AdminWeb/
│   └── main.py
└── token_shop_backend/
    ├── .env
    └── app/
```

## Logs

Nếu dùng `run_all_services.py`:
- Logs: `service_logs/adminweb.log`

Nếu chạy trực tiếp:
- Logs hiển thị trên console

## Production Deployment

### Khuyến nghị

1. **Dùng Uvicorn với workers**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2 --log-level info
   ```

2. **Dùng reverse proxy** (Nginx/Apache):
   - Proxy requests đến `http://localhost:8001`
   - SSL/TLS termination
   - Static files caching

3. **Dùng process manager** (NSSM trên Windows, systemd trên Linux):
   - Auto-restart khi crash
   - Chạy ngầm
   - Logging

### Ví dụ với NSSM (Windows)

```powershell
# Cài đặt NSSM service
nssm install AdminWeb "C:\Python\python.exe"
nssm set AdminWeb AppParameters "-m uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2"
nssm set AdminWeb AppDirectory "D:\NEW\CONGVIEC\Python\AdminWeb"
nssm set AdminWeb AppStdout "D:\NEW\CONGVIEC\Python\AdminWeb\logs\service.log"
nssm set AdminWeb AppStderr "D:\NEW\CONGVIEC\Python\AdminWeb\logs\service_error.log"
nssm set AdminWeb Start SERVICE_AUTO_START
nssm start AdminWeb
```

## So sánh các cách chạy

| Cách chạy | Workers | Auto-reload | Logging | Phù hợp |
|-----------|---------|-------------|---------|---------|
| `python main.py` | ❌ (1 worker) | ✅ | Console | Development |
| `uvicorn --workers 2` | ✅ (2 workers) | ❌ | Console | Production |
| `run_all_services.py` | ✅ (2 workers) | ❌ | File | **Khuyến nghị** |

## Lưu ý

1. **Security**: Đổi password mặc định trong production
2. **Database**: Đảm bảo database từ token_shop_backend đã được setup
3. **Port**: Port 8001 không được sử dụng bởi service khác
4. **Workers**: Dùng 2-4 workers tùy CPU và RAM
5. **SSL**: Dùng HTTPS trong production (qua reverse proxy)

## Liên kết

- Backend API: http://localhost:8000 (token_shop_backend)
- Telegram Bot: APITELE (chạy riêng)
- Service Manager: `run_all_services.py` (quản lý tất cả)
