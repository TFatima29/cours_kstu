@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Course Platform
if not exist ".venv\Scripts\python.exe" (
  echo Создаю окружение и ставлю библиотеки, это один раз...
  py -V:3.13 -m venv .venv || python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  ".venv\Scripts\python.exe" manage.py migrate
  ".venv\Scripts\python.exe" manage.py seed_demo
)
".venv\Scripts\python.exe" manage.py migrate --noinput >nul
start "" http://127.0.0.1:8000/
echo Сайт: http://127.0.0.1:8000/   Остановить: закройте это окно или Ctrl+C
".venv\Scripts\python.exe" manage.py runserver
pause
