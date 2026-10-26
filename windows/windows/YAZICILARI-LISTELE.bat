@echo off
if exist "C:\ServisDefteri\venv\Scripts\python.exe" (cd /d "C:\ServisDefteri") else (cd /d "%~dp0..")
set PYTHONUTF8=1
venv\Scripts\python.exe scripts\yazicilari_listele.py
echo.
pause
