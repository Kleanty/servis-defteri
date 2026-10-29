@echo off
rem Dis sistem API DEMO testi. Yonetici gerekmez. Demo kayitlar silinmez; isin bitince TEMIZLE secenegini kullan.
if exist "C:\ServisDefteri\venv\Scripts\python.exe" (cd /d "C:\ServisDefteri") else (cd /d "%~dp0..")
set PYTHONUTF8=1
echo === 1) YEREL deneme (demo kayitlar eklenir, API denenir) ===
venv\Scripts\python.exe scripts\entegrasyon_deneme.py
echo.
echo === 2) INTERNET uzerinden deneme (.env icindeki PUBLIC_BASE_URL; domain baglanmadiysa hata verir, onemli degil) ===
venv\Scripts\python.exe scripts\entegrasyon_deneme.py --internet --hafif
echo.
echo Demo kayitlari uygulamada incele. Silmek icin bu pencerede E yaz, Enter bas; silmeden cikmak icin sadece Enter.
set /p SIL=Demo kayitlar silinsin mi (E/H)? 
if /i "%SIL%"=="E" venv\Scripts\python.exe scripts\entegrasyon_deneme.py --temizle
pause
