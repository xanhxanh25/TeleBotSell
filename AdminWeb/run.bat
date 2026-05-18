@echo off
REM Script chạy AdminWeb (Windows Batch)
REM Sử dụng: run.bat

echo [*] Đang khởi động AdminWeb...

REM Lấy thư mục gốc project (parent của AdminWeb)
cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0.."
set "APITELE_VENV=%PROJECT_ROOT%\APITELE\.venv"

REM Kiểm tra và activate virtual environment từ APITELE
if exist "%APITELE_VENV%\Scripts\activate.bat" (
    echo [OK] Tìm thấy virtual environment từ APITELE\.venv
    call "%APITELE_VENV%\Scripts\activate.bat"
) else (
    echo [!] Không tìm thấy .venv từ APITELE, sử dụng Python global
)

REM Chuyển về thư mục AdminWeb
cd /d "%~dp0"

REM Kiểm tra file main.py
if not exist "main.py" (
    echo [ERROR] Không tìm thấy file main.py!
    exit /b 1
)

echo [*] Đang chạy AdminWeb...
echo [*] Truy cập: http://localhost:8001
echo.

REM Chạy AdminWeb
python main.py
