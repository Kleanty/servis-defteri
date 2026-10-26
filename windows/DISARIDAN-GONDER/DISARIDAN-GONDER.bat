@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where py >nul 2>&1 && (py -3 disaridan_gonder.py & goto bitti)
where python >nul 2>&1 && (python disaridan_gonder.py & goto bitti)
echo Bu bilgisayarda Python yok. https://www.python.org/downloads/ adresinden kur
echo (kurarken "Add python.exe to PATH" kutusunu isaretle), sonra bu dosyayi tekrar calistir.
:bitti
echo.
pause
