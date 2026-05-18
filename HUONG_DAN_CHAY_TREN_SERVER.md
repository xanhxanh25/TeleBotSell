# Hướng dẫn chạy trên Server Ubuntu

## Bước 1: SSH vào server

Từ máy Windows, mở PowerShell hoặc CMD và chạy:

```bash
ssh root@36.50.176.15
```

Nếu server yêu cầu password, nhập password của user root.
Nếu dùng SSH key, đảm bảo key đã được cấu hình.

## Bước 2: Di chuyển vào thư mục /opt

Sau khi SSH thành công, chạy:

```bash
cd /opt
```

Kiểm tra các file đã có:

```bash
ls -la
```

Bạn sẽ thấy:
- AdminWeb/
- APITELE/
- token_shop_backend/
- TokenPay/
- setup_ubuntu.sh
- start_all.sh
- stop_all.sh

## Bước 3: Cấp quyền thực thi cho scripts

```bash
chmod +x setup_ubuntu.sh start_all.sh stop_all.sh
```

## Bước 4: Chạy setup (chỉ cần chạy 1 lần đầu)

```bash
bash setup_ubuntu.sh
```

Lưu ý: Script này có thể cần quyền sudo. Nếu chạy với user root thì không cần sudo.

## Bước 5: Tạo virtual environments và cài dependencies

### APITELE
```bash
cd /opt/APITELE
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd /opt
```

### token_shop_backend
```bash
cd /opt/token_shop_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd /opt
```

### AdminWeb
```bash
cd /opt/AdminWeb
pip install -r requirements.txt
cd /opt
```

## Bước 6: Cấu hình các services

### APITELE - Tạo file .env
```bash
cd /opt/APITELE
nano .env
# Hoặc dùng vi: vi .env
# Thêm BOT_TOKEN và các cấu hình cần thiết
```

### token_shop_backend - Tạo file .env
```bash
cd /opt/token_shop_backend
nano .env
# Cấu hình DATABASE_URL và các biến môi trường khác
```

### TokenPay - Cấu hình appsettings.json
```bash
cd /opt/TokenPay/src/TokenPay
# Kiểm tra và chỉnh sửa appsettings.json nếu cần
nano appsettings.json
```

## Bước 7: Chạy tất cả services

```bash
cd /opt
bash start_all.sh
```

## Bước 8: Kiểm tra services đang chạy

```bash
# Xem logs
tail -f logs/apitele/service.log
tail -f logs/backend/service.log
tail -f logs/adminweb/service.log
tail -f logs/tokenpay/service.log

# Hoặc xem processes
ps aux | grep -E "(python|dotnet|uvicorn)"
```

## Dừng services

```bash
cd /opt
bash stop_all.sh
```

## Lưu ý

1. **Quyền root**: Nếu bạn đang dùng user root (như trong hình), không cần sudo
2. **Firewall**: Đảm bảo các ports 8000, 8001, 5001 đã được mở:
   ```bash
   sudo ufw allow 8000/tcp
   sudo ufw allow 8001/tcp
   sudo ufw allow 5001/tcp
   ```
3. **Permissions**: Đảm bảo các scripts có quyền thực thi: `chmod +x *.sh`
4. **Database**: Đảm bảo PostgreSQL đã được cài đặt và chạy (nếu backend cần)

## Troubleshooting

### Không thể SSH vào server
- Kiểm tra địa chỉ IP: `36.50.176.15`
- Kiểm tra port SSH (mặc định 22)
- Kiểm tra firewall trên server

### Scripts không chạy được
```bash
# Kiểm tra quyền
ls -la *.sh

# Cấp quyền nếu cần
chmod +x *.sh

# Kiểm tra lỗi syntax
bash -n start_all.sh
```

### Services không khởi động
```bash
# Xem log lỗi
tail -f logs/*/error.log

# Kiểm tra ports có bị chiếm
sudo netstat -tulpn | grep -E ':(8000|8001|5001)'
```
