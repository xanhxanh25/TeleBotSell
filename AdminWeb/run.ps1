# Set UTF-8 encoding cho PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# Script chạy AdminWeb
# Sử dụng: .\run.ps1

Write-Host "[*] Đang khởi động AdminWeb..." -ForegroundColor Cyan

# Lấy thư mục gốc project (parent của AdminWeb)
$projectRoot = Split-Path -Parent $PSScriptRoot
$apiteleVenv = Join-Path $projectRoot "APITELE\.venv"

# Kiểm tra và activate virtual environment từ APITELE
if (Test-Path $apiteleVenv) {
    Write-Host "[OK] Tìm thấy virtual environment từ APITELE\.venv" -ForegroundColor Green
    & (Join-Path $apiteleVenv "Scripts\Activate.ps1")
} else {
    Write-Host "[!] Không tìm thấy .venv từ APITELE, sử dụng Python global" -ForegroundColor Yellow
}

# Chuyển về thư mục AdminWeb
Set-Location $PSScriptRoot

# Kiểm tra file main.py
if (-not (Test-Path "main.py")) {
    Write-Host "[ERROR] Không tìm thấy file main.py!" -ForegroundColor Red
    exit 1
}

Write-Host "[*] Đang chạy AdminWeb..." -ForegroundColor Cyan
Write-Host "[*] Truy cập: http://localhost:8001" -ForegroundColor Green
Write-Host ""

# Chạy AdminWeb
python main.py
