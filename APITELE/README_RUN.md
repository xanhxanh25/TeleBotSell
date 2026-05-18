# Hướng dẫn chạy bot ổn định

Có nhiều cách để chạy bot ổn định hơn PowerShell thông thường:

## 1. Chạy như Windows Service (Khuyến nghị - Ổn định nhất)

### Cài đặt NSSM (Non-Sucking Service Manager)

**Cách 1: Tự động tải và cài đặt (Khuyến nghị)**
```powershell
cd APITELE
.\download_nssm.ps1
```

**Cách 2: Tải thủ công**
- Tải từ: https://nssm.cc/download
- Giải nén vào `C:\nssm\`
- Hoặc đặt `nssm.exe` vào thư mục có trong PATH

### Cài đặt service

```powershell
cd APITELE
.\install_service.ps1
```

Service sẽ:
- Tự động khởi động khi Windows start
- Tự động restart khi crash
- Chạy ngầm, không cần PowerShell
- Ghi log vào `logs/service.log` và `logs/service_error.log`

### Quản lý service

```powershell
# Khởi động
net start TelegramBot

# Dừng
net stop TelegramBot

# Xem trạng thái
sc query TelegramBot

# Gỡ cài đặt
C:\nssm\nssm.exe remove TelegramBot confirm
```

## 2. Chạy với Auto-restart (Không cần NSSM)

```powershell
cd APITELE
.\run_background.ps1
```

Script sẽ:
- Chạy bot ở background
- Tự động restart khi crash
- Ghi log vào `logs/bot_background.log`
- Nhấn Ctrl+C để dừng

## 3. Dùng Task Scheduler (Windows built-in)

1. Mở Task Scheduler
2. Tạo Task mới:
   - Name: `TelegramBot`
   - Trigger: "At startup" hoặc "At log on"
   - Action: Start a program
     - Program: `python`
     - Arguments: `run.py`
     - Start in: `C:\path\to\APITELE`
   - Settings: 
     - ✅ Run whether user is logged on or not
     - ✅ Run with highest privileges
     - ✅ Restart the task if it fails
     - Delay: 30 seconds

Hoặc dùng file `run_service.bat`:

```powershell
# Tạo task từ command line
schtasks /create /tn "TelegramBot" /tr "C:\path\to\APITELE\run_service.bat" /sc onstart /ru SYSTEM /rl HIGHEST /f
```

## 4. Dùng PM2 (Nếu có Node.js)

```bash
# Cài đặt PM2
npm install -g pm2

# Cài đặt pm2-windows-startup để tự động start khi Windows boot
pm2 startup

# Chạy bot
cd APITELE
pm2 start run.py --name telegram-bot --interpreter python --restart-delay=5000

# Lưu cấu hình
pm2 save
```

## 5. Dùng Screen (Nếu có WSL hoặc Linux)

```bash
# Cài đặt screen
sudo apt install screen

# Chạy bot trong screen session
screen -S telegram-bot
cd APITELE
python run.py

# Detach: Ctrl+A, sau đó D
# Attach lại: screen -r telegram-bot
```

## So sánh các phương pháp

| Phương pháp | Ổn định | Auto-restart | Chạy ngầm | Dễ setup |
|------------|---------|--------------|-----------|----------|
| **NSSM Service** | ⭐⭐⭐⭐⭐ | ✅ | ✅ | ⭐⭐⭐ |
| **Background Script** | ⭐⭐⭐⭐ | ✅ | ❌ | ⭐⭐⭐⭐⭐ |
| **Task Scheduler** | ⭐⭐⭐⭐ | ✅ | ✅ | ⭐⭐⭐ |
| **PM2** | ⭐⭐⭐⭐⭐ | ✅ | ✅ | ⭐⭐⭐⭐ |
| **Screen** | ⭐⭐⭐ | ❌ | ✅ | ⭐⭐⭐⭐⭐ |

## Khuyến nghị

**Cho production:** Dùng **NSSM Service** (cách 1) - ổn định nhất, tự động restart, chạy ngầm.

**Cho development:** Dùng **Background Script** (cách 2) - đơn giản, dễ debug.

## Lưu ý

- Tất cả các phương pháp đều **chỉ chặn từng cá nhân spam** (mỗi user_id có ban riêng)
- Bot sẽ tự động restart khi crash (trừ khi dừng bình thường với Ctrl+C)
- Logs sẽ được ghi vào thư mục `logs/`

