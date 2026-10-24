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
schtasks /end /tn "ServisDefteri" >nul 2>&1
timeout /t 3 /nobreak >nul
schtasks /run /tn "ServisDefteri"
echo Uygulama yeniden baslatildi. Birkac saniye sonra tarayicidan acabilirsin.
timeout /t 5 /nobreak >nul
