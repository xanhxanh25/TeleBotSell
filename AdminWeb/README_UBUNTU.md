# Hướng dẫn chạy BOTTELE trên Ubuntu 24.04

## Yêu cầu hệ thống

- Ubuntu 24.04 (hoặc Ubuntu 22.04+)
- Quyền sudo
- Kết nối internet

## Cài đặt môi trường

### Bước 1: Cài đặt dependencies

```bash
bash setup_ubuntu.sh
```

Script này sẽ cài đặt:
- Python 3.11+ và pip
- .NET 8.0 SDK (cho TokenPay)
- PostgreSQL client
- Supervisor (để quản lý services)
- Các công cụ cần thiết khác

### Bước 2: Tạo virtual environments

```bash
# Virtual environment cho APITELE
cd APITELE
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Virtual environment cho token_shop_backend
cd token_shop_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# AdminWeb có thể dùng venv từ APITELE hoặc cài riêng
cd AdminWeb
pip install -r requirements.txt
cd ..
```

### Bước 3: Cấu hình các services

#### APITELE
```bash
cd APITELE
# Tạo file .env từ .env.example (nếu có)
# Hoặc tạo file .env với BOT_TOKEN và các cấu hình cần thiết
```

#### token_shop_backend
```bash
cd token_shop_backend
# Tạo file .env từ .env.example (nếu có)
# Cấu hình DATABASE_URL và các biến môi trường khác
```

#### TokenPay
```bash
cd TokenPay/src/TokenPay
# Đảm bảo có file appsettings.json và EVMChains.json
# Copy từ .Example nếu chưa có
```

## Chạy services

### Chạy tất cả services cùng lúc

```bash
bash start_all.sh
```

Script sẽ khởi động 4 services:
1. **APITELE** - Telegram Bot
2. **Backend** - token_shop_backend (port 8000)
3. **AdminWeb** - Admin Panel (port 8001)
4. **TokenPay** - Payment Gateway (port 5001)

Mỗi service chạy trong background với:
- Auto-restart khi crash
- Logging riêng biệt
- Quản lý process độc lập

### Xem logs

```bash
# Xem log real-time
tail -f logs/apitele/service.log
tail -f logs/backend/service.log
tail -f logs/adminweb/service.log
tail -f logs/tokenpay/service.log

# Xem log lỗi
tail -f logs/apitele/error.log
tail -f logs/backend/error.log
tail -f logs/adminweb/error.log
tail -f logs/tokenpay/error.log
```

### Dừng tất cả services

```bash
bash stop_all.sh
```

## Chạy từng service riêng lẻ

### APITELE
```bash
cd APITELE
source .venv/bin/activate  # Nếu dùng venv
python run.py
```

### Backend
```bash
cd token_shop_backend
source .venv/bin/activate  # Nếu dùng venv
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### AdminWeb
```bash
cd AdminWeb
# Dùng venv từ APITELE hoặc python3 global
python main.py
```

### TokenPay
```bash
cd TokenPay/src/TokenPay
dotnet run --urls=http://0.0.0.0:5001
```

## Ports

- **Backend**: 8000
- **AdminWeb**: 8001
- **TokenPay**: 5001
- **APITELE**: Telegram Bot (không cần port)

## Troubleshooting

### .NET SDK chưa được cài đặt
```bash
bash setup_ubuntu.sh
# Hoặc cài thủ công:
wget https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt update
sudo apt install -y dotnet-sdk-8.0
```

### Virtual environment không hoạt động
```bash
# Tạo lại venv
cd APITELE  # hoặc token_shop_backend
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Services không khởi động
- Kiểm tra logs: `tail -f logs/<service_name>/error.log`
- Kiểm tra file .env có tồn tại và đúng định dạng
- Kiểm tra ports có bị chiếm dụng: `sudo netstat -tulpn | grep -E ':(8000|8001|5001)'`
- Kiểm tra dependencies đã cài đủ: `pip list` hoặc `dotnet --version`

### Services crash liên tục
- Kiểm tra logs để xem lỗi cụ thể
- Kiểm tra cấu hình (database connection, API keys, etc.)
- Kiểm tra tài nguyên hệ thống (RAM, disk space)

## Lưu ý

- **TokenPay.db**: File database quan trọng, chứa private keys. **PHẢI BACKUP** thường xuyên!
- Scripts sử dụng `nohup` và background processes, phù hợp cho production
- Để chạy như systemd services (khởi động cùng hệ thống), có thể tạo systemd service files
- Đảm bảo firewall cho phép các ports cần thiết

## Production Deployment

Để chạy ổn định trong production, nên sử dụng:

1. **systemd services** - Tự động khởi động khi reboot
2. **Supervisor** - Quản lý processes tốt hơn
3. **Nginx reverse proxy** - Cho AdminWeb và TokenPay
4. **SSL/TLS certificates** - Cho các web services
