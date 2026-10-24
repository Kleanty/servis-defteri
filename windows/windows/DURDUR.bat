@echo off
fltmc >nul 2>&1
if errorlevel 1 (
  echo Bu dosyayi YONETICI olarak calistir: sag tikla - "Yonetici olarak calistir".
  pause
  exit /b 1
)
schtasks /end /tn "ServisDefteri"
echo Uygulama durduruldu. Tekrar baslatmak icin YENIDEN-BASLAT.bat calistir.
pause
