@echo off
setlocal
cd /d "%~dp0.."
if not exist data mkdir data
set "LOG=%CD%\data\1-kur.log"
set "RAPOR=%CD%\data\kurulum-hata.txt"
echo ============================================== > "%LOG%"
echo   Servis Defteri - Windows kurulumu  %date% %time% >> "%LOG%"
echo ============================================== >> "%LOG%"
echo ==============================================
echo   Servis Defteri - Windows kurulumu
echo ==============================================
set "ADIM=0/4 Python kontrolu"
set "PY="
rem Once uyumlu surumler (3.12 > 3.11 > 3.10) py baslaticisiyla; yoksa PATH'teki python. Microsoft Store'un sahte python kisayolu "calismayan python" sayilir.
where py >nul 2>nul && (
  for %%v in (3.12 3.11 3.10) do if not defined PY (py -%%v -c "import sys" >nul 2>nul && set "PY=py -%%v")
)
if not defined PY where python >nul 2>nul && (python -c "import sys" >nul 2>nul && set "PY=python")
if not defined PY goto yok
%PY% -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<(3,13) else 1)" >nul 2>nul
if errorlevel 1 goto eski
set "ADIM=1/4 Sanal ortam"
echo [1/4] Sanal ortam hazirlaniyor...
if not exist venv\Scripts\python.exe %PY% -m venv venv >> "%LOG%" 2>&1
if errorlevel 1 goto hata
set "ADIM=2/4 Paketler (pip)"
echo [2/4] Gerekli paketler kuruluyor (internet gerekir, birkac dakika surebilir)...
venv\Scripts\python.exe -m pip install --disable-pip-version-check --quiet --upgrade pip >> "%LOG%" 2>&1
venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 goto hata
set "ADIM=3/4 Ayar dosyasi"
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
set "ADIM=0/4 Python kontrolu"
echo Python bulunamadi. https://www.python.org/downloads/ adresinden Python 3.12 kur.
echo Kurulumda en altaki "Add python.exe to PATH" kutusunu ISARETLE. Sonra bu dosyayi tekrar calistir.
echo ^(Microsoft Store'daki sahte python kisayolu varsa: Ayarlar - Uygulamalar - Uygulama yurutme takma adlari: python.exe ve python3.exe'yi kapat.^)
call :rapor "Python bulunamadi"
pause
exit /b 1
:eski
echo Python surumu uygun degil. Python 3.10, 3.11 veya 3.12 gerekir (3.12 onerilir; 3.13 ve sonrasi paketlerle uyumsuz olabilir).
call :rapor "Python surumu uygun degil (3.10-3.12 gerekir)"
pause
exit /b 1
:hata
echo.
echo HATA: "%ADIM%" adiminda sorun olustu.
echo Son satirlar (tam kayit: %LOG%):
powershell -NoProfile -Command "if (Test-Path '%LOG%') { Get-Content '%LOG%' -Tail 15 }"
echo.
echo Olasi nedenler: internet yok / proxy / antivirus pip'i engelliyor / diskte yer yok / "Yonetici olarak calistir" gerekiyor.
call :rapor "Adim basarisiz: %ADIM%"
pause
exit /b 1
:rapor
rem Tek dosyada: adim, bilgisayar bilgisi, kaydin sonu. Sorun giderirken bu dosyayi gonder.
> "%RAPOR%" echo Servis Defteri 1-KUR.bat hata raporu  %date% %time%
>> "%RAPOR%" echo Hata   : %~1
>> "%RAPOR%" echo Adim   : %ADIM%
>> "%RAPOR%" echo Klasor : %CD%
>> "%RAPOR%" echo Python : %PY%
>> "%RAPOR%" ver
>> "%RAPOR%" echo --- python surumu ---
if defined PY %PY% --version >> "%RAPOR%" 2>&1
>> "%RAPOR%" echo --- py listesi ---
py -0p >> "%RAPOR%" 2>&1
>> "%RAPOR%" echo --- kurulum kaydi ---
type "%LOG%" >> "%RAPOR%" 2>nul
echo.
echo Hata raporu: %RAPOR%   ^(sorunu cozemezsen bu dosyayi gonder^)
exit /b 0
