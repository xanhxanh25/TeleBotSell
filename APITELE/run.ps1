# Set UTF-8 encoding cho PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# Script chay bot Telegram
# Su dung: .\run.ps1

Write-Host "[*] Dang khoi dong bot Telegram..." -ForegroundColor Cyan

# Kiem tra xem da co virtual environment chua
if (Test-Path ".venv") {
    Write-Host "[OK] Tim thay virtual environment (.venv)" -ForegroundColor Green
    # Activate virtual environment
    & ".venv\Scripts\Activate.ps1"
} else {
    Write-Host "[!] Khong tim thay .venv, su dung Python global" -ForegroundColor Yellow
}

# Kiem tra file .env
if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] Khong tim thay file .env!" -ForegroundColor Red
    Write-Host "Vui long tao file .env voi BOT_TOKEN va cac cau hinh can thiet." -ForegroundColor Yellow
    exit 1
}

# Kiem tra thu muc logs
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
    Write-Host "[OK] Da tao thu muc logs" -ForegroundColor Green
}

Write-Host "[*] Dang kiem tra dependencies..." -ForegroundColor Cyan
# Kiem tra xem aiogram da duoc cai chua
$aiogramInstalled = python -c "import aiogram" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] aiogram chua duoc cai dat. Dang cai dat dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip
    if (Test-Path "requirements.txt") {
        python -m pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Da cai dat dependencies thanh cong!" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Loi khi cai dat dependencies!" -ForegroundColor Red
            Write-Host "Vui long chay thu cong: pip install -r requirements.txt" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "[ERROR] Khong tim thay requirements.txt!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[OK] Dependencies da duoc cai dat" -ForegroundColor Green
}

Write-Host "[*] Dang chay bot..." -ForegroundColor Cyan
Write-Host "Nhan Ctrl+C de dung bot" -ForegroundColor Yellow
Write-Host ""

# Chay bot voi error handling tot hon
try {
    python -m app.main
} catch {
    Write-Host "[ERROR] Loi khi chay bot: $_" -ForegroundColor Red
    exit 1
} finally {
    Write-Host ""
    Write-Host "[*] Bot da dung." -ForegroundColor Yellow
}
