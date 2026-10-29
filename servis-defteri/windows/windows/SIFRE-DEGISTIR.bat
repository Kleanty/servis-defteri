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
if not exist venv\Scripts\python.exe (
  echo Program bulunamadi. Once SERVIS-DEFTERI-KUR.bat ile kurulum yapilmali.
  pause
  exit /b 1
)
venv\Scripts\python.exe scripts\sifre_degistir.py
set SONUC=%errorlevel%
echo.
if "%SONUC%"=="0" (
  schtasks /query /tn "ServisDefteri" >nul 2>&1
  if errorlevel 1 (
    echo Sifre degisti. Uygulama otomatik baslatma gorevi olarak kurulu degil: calisiyorsa 2-BASLAT.bat penceresini kapatip yeniden ac.
  ) else (
    echo Sifre degisti. Yeni sifre simdi gecerli: uygulama yeniden baslatiliyor...
    schtasks /end /tn "ServisDefteri" >nul 2>&1
    timeout /t 3 /nobreak >nul
    schtasks /run /tn "ServisDefteri" >nul 2>&1
  )
) else (
  echo Sifre DEGISMEDI. Eski sifre gecerli.
)
pause
