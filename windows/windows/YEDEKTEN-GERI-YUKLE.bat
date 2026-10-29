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
set PYTHONUTF8=1
if not exist "C:\ServisDefteri\venv\Scripts\python.exe" (
  echo C:\ServisDefteri bulunamadi. Once SERVIS-DEFTERI-KUR.bat ile kurulum yapilmali.
  pause
  exit /b 1
)
cd /d C:\ServisDefteri
echo Uygulama durduruluyor...
schtasks /end /tn "ServisDefteri" >nul 2>&1
timeout /t 4 /nobreak >nul
venv\Scripts\python.exe scripts\geri_yukle.py
set SONUC=%errorlevel%
echo.
echo Uygulama yeniden baslatiliyor...
schtasks /run /tn "ServisDefteri" >nul 2>&1
if not "%SONUC%"=="0" (
  echo.
  echo GERI YUKLEME TAMAMLANMADI veya iptal edildi. Mevcut kayitlar yerinde. Uygulama yeniden baslatildi.
) else (
  echo Bitti. Birkac saniye sonra tarayicidan acabilirsin.
)
pause
