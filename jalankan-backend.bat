@echo off
title HerbID - Backend (FastAPI)
echo ========================================================
echo   Memulai Backend HerbID (FastAPI pada Port 8000)...
echo ========================================================
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
pause
