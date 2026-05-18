# PowerShell run script (Windows Server 2022)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# copy .env.example -> .env then edit
if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Write-Host "✅ Created .env from .env.example. Please edit it." -ForegroundColor Yellow
}

# run
uvicorn app.main:app --host 0.0.0.0 --port 8000
