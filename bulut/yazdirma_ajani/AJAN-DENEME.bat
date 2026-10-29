@echo off
fltmc >nul 2>&1
if errorlevel 1 (
  echo Bu dosyayi YONETICI olarak calistir: dosyaya sag tikla - "Yonetici olarak calistir".
  echo ^(ayar dosyasi yalnizca Yonetici/SYSTEM erisimine kisitlidir^)
  pause
  exit /b 1
)
if exist "C:\ServisAjan\venv\Scripts\python.exe" (cd /d "C:\ServisAjan") else (cd /d "%~dp0")
set PYTHONUTF8=1
echo 1) Sunucu baglantisi:
venv\Scripts\python.exe yazdirma_ajani.py --baglanti
echo.
echo 2) Yazici:
venv\Scripts\python.exe yazdirma_ajani.py --durum
echo.
set /p CEVAP=Yazicidan deneme etiketi cikarilsin mi? [E/H]: 
if /i "%CEVAP%"=="E" venv\Scripts\python.exe yazdirma_ajani.py --deneme
echo.
echo Ajanin son kayitlari (C:\ServisAjan\ajan.log):
if exist ajan.log powershell -NoProfile -Command "Get-Content ajan.log -Tail 15"
pause
