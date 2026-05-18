# Set UTF-8 encoding cho PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# Script tai va cai dat NSSM tu dong

Write-Host "[*] Dang tai NSSM..." -ForegroundColor Cyan

$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$tempDir = "$env:TEMP\nssm_download"
$nssmDir = "C:\nssm"

# Tao thu muc temp
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Tao thu muc nssm neu chua co
if (-not (Test-Path $nssmDir)) {
    New-Item -ItemType Directory -Path $nssmDir | Out-Null
}

try {
    # Tai file zip
    $zipFile = Join-Path $tempDir "nssm.zip"
    Write-Host "Dang tai tu: $nssmUrl" -ForegroundColor Yellow
    Invoke-WebRequest -Uri $nssmUrl -OutFile $zipFile -UseBasicParsing
    
    # Giai nen
    Write-Host "Dang giai nen..." -ForegroundColor Yellow
    Expand-Archive -Path $zipFile -DestinationPath $tempDir -Force
    
    # Tim file nssm.exe trong thu muc giai nen
    $nssmExe = Get-ChildItem -Path $tempDir -Filter "nssm.exe" -Recurse | Select-Object -First 1
    
    if ($nssmExe) {
        # Copy vao C:\nssm
        Copy-Item $nssmExe.FullName -Destination "$nssmDir\nssm.exe" -Force
        Write-Host "[OK] Da cai dat NSSM vao: $nssmDir\nssm.exe" -ForegroundColor Green
        
        # Them vao PATH (neu chua co)
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        if ($currentPath -notlike "*$nssmDir*") {
            Write-Host "Dang them vao PATH..." -ForegroundColor Yellow
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$nssmDir", "Machine")
            Write-Host "[OK] Da them vao PATH. Can restart PowerShell de ap dung." -ForegroundColor Green
        }
    } else {
        Write-Host "[ERROR] Khong tim thay nssm.exe trong file zip!" -ForegroundColor Red
        exit 1
    }
    
    # Xoa thu muc temp
    Remove-Item $tempDir -Recurse -Force
    
    Write-Host ""
    Write-Host "[OK] Hoan thanh! Ban co the chay install_service.ps1 de cai dat service." -ForegroundColor Green
    
} catch {
    Write-Host "[ERROR] Loi khi tai/cai dat NSSM: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Vui long tai thu cong tu: https://nssm.cc/download" -ForegroundColor Yellow
    exit 1
}
