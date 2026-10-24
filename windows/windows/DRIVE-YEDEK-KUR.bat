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
chcp 65001 >nul
copy /y "%~dp0drive-yedek-kur.ps1" "%TEMP%\drive-yedek-kur.ps1" >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\drive-yedek-kur.ps1"
