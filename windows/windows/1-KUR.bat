@echo off
setlocal
cd /d "%~dp0.."
echo ==============================================
echo   Servis Defteri - Windows kurulumu
echo ==============================================
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto yok
%PY% -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2] else 1)" >nul 2>nul
if errorlevel 1 goto eski
echo [1/4] Sanal ortam hazirlaniyor...
if not exist venv\Scripts\python.exe %PY% -m venv venv
if errorlevel 1 goto hata
echo [2/4] Gerekli paketler kuruluyor (internet gerekir, birkac dakika surebilir)...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if errorlevel 1 goto hata
echo [3/4] Ayar dosyasi (.env)...
if not exist .env (copy /y .env.example .env >nul & echo     .env olusturuldu.) else echo     .env zaten var, dokunulmadi.
if not exist data mkdir data
echo [4/4] Bitti.
echo.
echo SIMDI: acilacak Not Defteri'nde isletme adini, telefonu ve alan adini yaz, kaydet ve kapat.
echo (Alan adini henuz almadiysan PUBLIC_BASE_URL satirina dokunma.)
pause
start /wait notepad .env
echo.
echo Siradaki adim: yazici kurulumu ve test icin WINDOWS-KURULUM.txt dosyasini oku.
echo Hemen denemek icin 2-BASLAT.bat dosyasini calistir.
pause
exit /b 0
:yok
echo Python bulunamadi. https://www.python.org/downloads/ adresinden Python 3.12 kur.
echo Kurulumda en altaki "Add python.exe to PATH" kutusunu ISARETLE. Sonra bu dosyayi tekrar calistir.
pause
exit /b 1
:eski
echo Python surumu cok eski. Python 3.10 veya daha yenisi gerekir (3.12 onerilir).
pause
exit /b 1
:hata
echo.
echo Kurulum sirasinda hata olustu. Yukaridaki mesaji kontrol et (internet baglantisi var mi?).
pause
exit /b 1
