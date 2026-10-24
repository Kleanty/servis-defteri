@echo off
fltmc >nul 2>&1
if errorlevel 1 (
  echo Bu dosyayi YONETICI olarak calistir: dosyaya sag tikla - "Yonetici olarak calistir".
  pause
  exit /b 1
)
for %%i in ("%~dp0..") do set "ROOT=%%~fi"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0otomatik-baslat.ps1" -Kok "%ROOT%"
if errorlevel 1 (
  echo Gorev olusturulamadi. Yukaridaki hata mesajini kontrol et.
  pause
  exit /b 1
)
echo.
echo Tarayicidan http://localhost:5000 adresini ac; calisiyorsa tamam.
pause
