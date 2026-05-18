@echo off
REM Script chạy bot như service (dùng Task Scheduler hoặc NSSM)
REM Chạy script này trong Task Scheduler với "Run whether user is logged on or not"

cd /d "%~dp0"

REM Kiểm tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python không được tìm thấy!
    pause
    exit /b 1
)

REM Kiểm tra .env
if not exist ".env" (
    echo ❌ Không tìm thấy file .env!
    pause
    exit /b 1
)

REM Tạo thư mục logs nếu chưa có
if not exist "logs" mkdir logs

REM Chạy bot (loop để tự restart)
:loop
python run.py
if errorlevel 1 (
    echo ⚠️ Bot crash, restart sau 5 giây...
    timeout /t 5 /nobreak >nul
    goto loop
)

echo ✅ Bot dừng bình thường
pause

