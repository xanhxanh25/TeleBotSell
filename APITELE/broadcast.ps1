# PowerShell script de chay broadcast tool voi virtual environment
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Message
)

Set-Location $PSScriptRoot

Write-Host "Kiem tra virtual environment..." -ForegroundColor Cyan

$venvDir = Join-Path $PSScriptRoot '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$pipExe = Join-Path $venvDir 'Scripts\pip.exe'
$scriptPath = Join-Path $PSScriptRoot 'broadcast.py'

if (-not (Test-Path $venvPython)) {
    Write-Host 'Virtual environment khong ton tai!' -ForegroundColor Yellow
    Write-Host 'Dang tao virtual environment...' -ForegroundColor Cyan
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Khong the tao virtual environment!' -ForegroundColor Red
        exit 1
    }
    Write-Host 'Da tao virtual environment' -ForegroundColor Green
}

Write-Host 'Kiem tra dependencies...' -ForegroundColor Cyan
$checkResult = & $venvPython -c 'import aiogram, sqlalchemy, psycopg2' 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Dang cai dat dependencies...' -ForegroundColor Cyan
    # Cài đặt dependencies từ cả APITELE và backend
    & $pipExe install aiogram sqlalchemy psycopg2-binary pydantic pydantic-settings python-dotenv
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Khong the cai dat dependencies!' -ForegroundColor Red
        exit 1
    }
    Write-Host 'Da cai dat dependencies' -ForegroundColor Green
} else {
    Write-Host 'Dependencies da san sang' -ForegroundColor Green
}

Write-Host ''
Write-Host 'Chay broadcast tool...' -ForegroundColor Cyan
Write-Host ''

if ($Message.Count -gt 0) {
    $messageText = $Message -join ' '
    $env:BROADCAST_MESSAGE = $messageText
    try {
        & $venvPython $scriptPath
    } finally {
        if (Test-Path Env:BROADCAST_MESSAGE) {
            Remove-Item Env:BROADCAST_MESSAGE
        }
    }
} else {
    & $venvPython $scriptPath
}
