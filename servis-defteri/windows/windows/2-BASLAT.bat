@echo off
cd /d "%~dp0.."
if not exist venv\Scripts\python.exe (
  echo Once 1-KUR.bat calistirilmali.
  pause
  exit /b 1
)
echo Servis Defteri calisiyor. Bu pencereyi KAPATMA (kapatinca uygulama durur).
echo Tarayicidan ac:  http://localhost:5000      Durdurmak icin: Ctrl+C
echo.
venv\Scripts\python.exe scripts\calistir.py
pause
