@echo off
fltmc >nul 2>&1
if errorlevel 1 (
  if "%~1"=="elev" (
    echo Yonetici izni alinamadi. Dosyaya sag tikla - "Yonetici olarak calistir".
    pause
    exit /b 1
  )
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList 'elev' -Verb RunAs"
  exit /b
)
if exist "C:\ServisDefteri\venv\Scripts\python.exe" (cd /d "C:\ServisDefteri") else (cd /d "%~dp0..")
set PYTHONUTF8=1
venv\Scripts\python.exe scripts\yedek.py
pause
