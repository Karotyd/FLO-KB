@echo off
cd /d %~dp0

call venv\Scripts\activate

python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload --workers 1
