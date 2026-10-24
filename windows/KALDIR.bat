@echo off
rem Servis Defteri - KALDIRMA (kurulumun tersi). Cift tikla; yonetici izni sorarsa "Evet" de.
fltmc >nul 2>&1
if errorlevel 1 (
  if "%~1"=="elev" (
    echo Yonetici izni alinamadi. Dosyaya sag tikla - "Yonetici olarak calistir".
    pause
    exit /b 1
  )
  echo Yonetici izni isteniyor...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList 'elev' -Verb RunAs"
  exit /b
)
if not exist "%~dp0windows\kaldir.ps1" (
  echo windows\kaldir.ps1 bulunamadi. KALDIR.bat dosyasini paket klasorunun icinden calistir.
  pause
  exit /b 1
)
rem Betik, silinecek klasorun DISINDA (TEMP) calisir: kendi bulundugu klasoru silerken takilmasin.
copy /y "%~dp0windows\kaldir.ps1" "%TEMP%\servis-defteri-kaldir.ps1" >nul
cd /d "%TEMP%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\servis-defteri-kaldir.ps1" & exit /b
