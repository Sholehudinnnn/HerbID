@echo off
title HerbID - Fullstack Runner
echo ========================================================
echo   Memulai HerbID Fullstack (Backend + Frontend)...
echo ========================================================
start "HerbID - Backend" cmd /k "py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload"
start "HerbID - Frontend" cmd /k "cd frontend && npm run dev"
echo.
echo Kedua server sedang dijalankan di jendela terpisah!
echo   - Backend URL  : http://127.0.0.1:8000
echo   - Frontend URL : http://localhost:5173
echo   - Swagger Docs : http://127.0.0.1:8000/docs
echo.
echo Silakan buka browser Anda di http://localhost:5173
echo.
pause
