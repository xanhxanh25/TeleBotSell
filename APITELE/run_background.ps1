# Set UTF-8 encoding cho PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# Script chay bot o background (khong can NSSM)
# Bot se chay ngam va tu dong restart khi crash

Write-Host "[*] Khoi dong bot o background mode..." -ForegroundColor Cyan

$scriptPath = Join-Path $PSScriptRoot "run.py"
$logFile = Join-Path $PSScriptRoot "logs\bot_background.log"
$errorFile = Join-Path $PSScriptRoot "logs\bot_background_error.log"

# Dam bao thu muc logs ton tai
$logsDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

# Kiem tra Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python khong duoc tim thay!" -ForegroundColor Red
    exit 1
}

# Kiem tra file .env
if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] Khong tim thay file .env!" -ForegroundColor Red
    exit 1
}

Write-Host "[*] Logs se duoc ghi vao:" -ForegroundColor Cyan
Write-Host "  - Output: $logFile" -ForegroundColor White
Write-Host "  - Errors: $errorFile" -ForegroundColor White
Write-Host ""
Write-Host "[!] Nhan Ctrl+C de dung bot" -ForegroundColor Yellow
Write-Host ""

# Ham restart bot khi crash
function Start-BotWithRestart {
    $maxRestarts = 1000
    $restartDelay = 5
    $restartCount = 0
    
    while ($restartCount -lt $maxRestarts) {
        $restartCount++
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        
        if ($restartCount -gt 1) {
            Write-Host "[$timestamp] [*] Restarting bot (lan $restartCount)... Doi $restartDelay giay..." -ForegroundColor Yellow
            Add-Content -Path $logFile -Value "[$timestamp] Restarting bot (attempt $restartCount)..." -Encoding UTF8
            Start-Sleep -Seconds $restartDelay
        } else {
            Write-Host "[$timestamp] [*] Starting bot..." -ForegroundColor Green
            Add-Content -Path $logFile -Value "[$timestamp] Starting bot..." -Encoding UTF8
        }
        
        try {
            # Chay bot va ghi log real-time (khong block)
            $process = Start-Process -FilePath "python" -ArgumentList "`"$scriptPath`"" -NoNewWindow -PassThru -RedirectStandardOutput "$env:TEMP\bot_stdout.txt" -RedirectStandardError "$env:TEMP\bot_stderr.txt"
            
            # Doi process ket thuc
            $process.WaitForExit()
            $exitCode = $process.ExitCode
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            
            # Doc va ghi stdout va stderr vao log
            if (Test-Path "$env:TEMP\bot_stdout.txt") {
                try {
                    $stdout = Get-Content "$env:TEMP\bot_stdout.txt" -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
                    if ($stdout -and $stdout.Trim()) {
                        Add-Content -Path $logFile -Value $stdout -Encoding UTF8 -NoNewline
                        Write-Host $stdout -NoNewline
                    }
                } catch {
                    # Neu khong doc duoc UTF8, thu ASCII
                    $stdout = Get-Content "$env:TEMP\bot_stdout.txt" -Raw -Encoding ASCII -ErrorAction SilentlyContinue
                    if ($stdout) {
                        Add-Content -Path $logFile -Value $stdout -Encoding UTF8 -NoNewline
                    }
                }
            }
            if (Test-Path "$env:TEMP\bot_stderr.txt") {
                try {
                    $stderr = Get-Content "$env:TEMP\bot_stderr.txt" -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
                    if ($stderr -and $stderr.Trim()) {
                        Add-Content -Path $errorFile -Value $stderr -Encoding UTF8 -NoNewline
                        Write-Host $stderr -ForegroundColor Red -NoNewline
                    }
                } catch {
                    # Neu khong doc duoc UTF8, thu ASCII
                    $stderr = Get-Content "$env:TEMP\bot_stderr.txt" -Raw -Encoding ASCII -ErrorAction SilentlyContinue
                    if ($stderr) {
                        Add-Content -Path $errorFile -Value $stderr -Encoding UTF8 -NoNewline
                    }
                }
            }
            
            if ($exitCode -eq 0) {
                Write-Host "[$timestamp] [OK] Bot dung binh thuong (exit code: $exitCode)" -ForegroundColor Green
                Add-Content -Path $logFile -Value "`n[$timestamp] Bot stopped normally (exit code: $exitCode)`n" -Encoding UTF8
                break  # Thoat loop neu bot dung binh thuong
            } else {
                Write-Host "`n[$timestamp] [!] Bot crash (exit code: $exitCode) - Se restart..." -ForegroundColor Yellow
                Add-Content -Path $errorFile -Value "`n[$timestamp] Bot crash (exit code: $exitCode)`n" -Encoding UTF8
            }
        } catch {
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            $errorMsg = $_.Exception.Message
            Write-Host "`n[$timestamp] [ERROR] Loi khi chay bot: $errorMsg" -ForegroundColor Red
            Add-Content -Path $errorFile -Value "`n[$timestamp] Error: $errorMsg`n" -Encoding UTF8
            $exitCode = 1  # Dat exit code de restart
        } finally {
            # Xoa file temp
            if (Test-Path "$env:TEMP\bot_stdout.txt") { Remove-Item "$env:TEMP\bot_stdout.txt" -ErrorAction SilentlyContinue }
            if (Test-Path "$env:TEMP\bot_stderr.txt") { Remove-Item "$env:TEMP\bot_stderr.txt" -ErrorAction SilentlyContinue }
        }
        
        # Neu exit code la 0 (dung binh thuong), khong restart
        if ($null -ne $exitCode -and $exitCode -eq 0) {
            break
        }
    }
    
    if ($restartCount -ge $maxRestarts) {
        Write-Host "[ERROR] Da dat so lan restart toi da ($maxRestarts). Dung bot." -ForegroundColor Red
    }
}

# Bat dau bot voi auto-restart
Start-BotWithRestart

Write-Host ""
Write-Host "[*] Bot da dung." -ForegroundColor Yellow
