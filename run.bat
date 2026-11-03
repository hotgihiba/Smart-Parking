@echo off
title ParkSmart - Smart Parking
cd /d "%~dp0"
if not exist .venv (
  echo Creating Python virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Starting ParkSmart. Make sure MongoDB Server is running.
echo Open http://127.0.0.1:5000 in your browser.
echo.
python app.py
pause
