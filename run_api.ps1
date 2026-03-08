$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

.\venv\Scripts\Activate.ps1

python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
