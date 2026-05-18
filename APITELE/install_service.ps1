# Set UTF-8 encoding cho PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# Script cai dat bot nhu Windows Service bang NSSM
# Yeu cau: Tai NSSM tu https://nssm.cc/download

Write-Host "[*] Cai dat bot nhu Windows Service" -ForegroundColor Cyan

# Tim NSSM o cac vi tri thuong gap
$nssmPaths = @(
    "C:\nssm\nssm.exe",
    "C:\Program Files\nssm\nssm.exe",
    "C:\Program Files (x86)\nssm\nssm.exe",
    "$env:ProgramFiles\nssm\nssm.exe",
    "$env:ProgramFiles(x86)\nssm\nssm.exe"
)

$nssmPath = $null
foreach ($path in $nssmPaths) {
    if (Test-Path $path) {
        $nssmPath = $path
        break
    }
}

# Tim trong PATH
if (-not $nssmPath) {
    try {
        $nssmInPath = Get-Command nssm -ErrorAction SilentlyContinue
        if ($nssmInPath) {
            $nssmPath = $nssmInPath.Source
        }
    } catch {
        # Khong tim thay trong PATH
    }
}

if (-not $nssmPath) {
    Write-Host "[!] NSSM chua duoc cai dat!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Vui long:" -ForegroundColor Yellow
    Write-Host "1. Tai NSSM tu: https://nssm.cc/download" -ForegroundColor White
    Write-Host "2. Giai nen vao C:\nssm\" -ForegroundColor White
    Write-Host "3. Hoac dat nssm.exe vao thu muc co trong PATH" -ForegroundColor White
    Write-Host ""
    Write-Host "Neu da cai dat o noi khac, chinh sua `$nssmPath trong script nay." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ban co muon mo trang download NSSM? (Y/N): " -ForegroundColor Cyan -NoNewline
    $openBrowser = Read-Host
    if ($openBrowser -eq "Y" -or $openBrowser -eq "y") {
        Start-Process "https://nssm.cc/download"
    }
    exit 1
}

Write-Host "[OK] Tim thay NSSM tai: $nssmPath" -ForegroundColor Green

$serviceName = "TelegramBot"
$pythonPath = (Get-Command python).Source
$scriptPath = Join-Path $PSScriptRoot "run.py"
$workingDir = $PSScriptRoot

Write-Host "[*] Thong tin cai dat:" -ForegroundColor Cyan
Write-Host "  Service Name: $serviceName" -ForegroundColor White
Write-Host "  Python: $pythonPath" -ForegroundColor White
Write-Host "  Script: $scriptPath" -ForegroundColor White
Write-Host "  Working Dir: $workingDir" -ForegroundColor White
Write-Host ""

# Xoa service cu neu co
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "[!] Service '$serviceName' da ton tai. Dang go cai dat..." -ForegroundColor Yellow
    Stop-Service -Name $serviceName -ErrorAction SilentlyContinue
    & $nssmPath remove $serviceName confirm
    Start-Sleep -Seconds 2
}

Write-Host "[*] Dang cai dat service..." -ForegroundColor Cyan

# Cai dat service
& $nssmPath install $serviceName $pythonPath "$scriptPath"

# Cau hinh service
& $nssmPath set $serviceName AppDirectory $workingDir
& $nssmPath set $serviceName Description "Telegram Bot Service - Auto restart on failure"
& $nssmPath set $serviceName Start SERVICE_AUTO_START
& $nssmPath set $serviceName AppStdout "$workingDir\logs\service.log"
& $nssmPath set $serviceName AppStderr "$workingDir\logs\service_error.log"
& $nssmPath set $serviceName AppRotateFiles 1
& $nssmPath set $serviceName AppRotateOnline 1
& $nssmPath set $serviceName AppRotateSeconds 86400
& $nssmPath set $serviceName AppRotateBytes 10485760

# Thiet lap auto restart khi crash
& $nssmPath set $serviceName AppExit Default Restart
& $nssmPath set $serviceName AppRestartDelay 5000
& $nssmPath set $serviceName AppThrottle 1500

Write-Host "[OK] Da cai dat service thanh cong!" -ForegroundColor Green
Write-Host ""
Write-Host "[*] Cac lenh quan ly service:" -ForegroundColor Cyan
Write-Host "  Start:   net start $serviceName" -ForegroundColor White
Write-Host "  Stop:    net stop $serviceName" -ForegroundColor White
Write-Host "  Restart: net stop $serviceName; net start $serviceName" -ForegroundColor White
Write-Host "  Status:  sc query $serviceName" -ForegroundColor White
Write-Host "  Uninstall: `"$nssmPath`" remove $serviceName confirm" -ForegroundColor White
Write-Host ""
Write-Host "[*] Ban co muon khoi dong service ngay? (Y/N): " -ForegroundColor Yellow -NoNewline
$answer = Read-Host
if ($answer -eq "Y" -or $answer -eq "y") {
    net start $serviceName
    Write-Host "[OK] Service da duoc khoi dong!" -ForegroundColor Green
}
