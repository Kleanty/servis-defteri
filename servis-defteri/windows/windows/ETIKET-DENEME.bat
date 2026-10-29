@echo off
if exist "C:\ServisDefteri\venv\Scripts\python.exe" (cd /d "C:\ServisDefteri") else (cd /d "%~dp0..")
set PYTHONUTF8=1
echo Yazicidan ornek bir etiket cikarilacak...
venv\Scripts\python.exe scripts\etiket_deneme.py
echo.
pause
