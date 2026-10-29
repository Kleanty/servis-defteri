@echo off
rem Servis Defteri - tek tikla kurulum. Cift tikla; yonetici izni sorarsa "Evet" de.
rem Hata olursa: ekranda adim + olasi neden yazar, C:\ServisDefteri\data\kurulum-hata.txt ve masaustune SERVIS-DEFTERI-KURULUM-HATASI.txt olusur.
rem Zip'in icinden calistirildiysa (gecici klasor) kurulum yarida kalir: once uyar.
echo "%~dp0" | findstr /i /c:"\AppData\Local\Temp" >nul
if not errorlevel 1 (
  echo.
  echo UYARI: Bu dosya zip'in icinden calistiriliyor gibi gorunuyor.
  echo Once zip dosyasina sag tikla - "Tumunu ayikla" de, cikan KLASORUN icinden tekrar calistir.
  echo.
  pause
  exit /b 1
)
fltmc >nul 2>&1
if errorlevel 1 (
  if "%~1"=="elev" (
    echo Yonetici izni alinamadi. Dosyaya sag tikla - "Yonetici olarak calistir".
    pause
    exit /b 1
  )
  echo Yonetici izni isteniyor...
  powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -ArgumentList 'elev' -Verb RunAs -ErrorAction Stop } catch { Write-Host 'Yonetici izni verilmedi ya da pencere acilamadi. Dosyaya sag tikla - Yonetici olarak calistir.' -ForegroundColor Red; exit 1 }"
  if errorlevel 1 pause
  exit /b
)
if not exist "%~dp0windows\kur.ps1" (
  echo HATA: windows\kur.ps1 bulunamadi. Zip eksik ayiklanmis olabilir; "Tumunu ayikla" ile yeniden cikar.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\kur.ps1"
set "SONUC=%errorlevel%"
echo.
if not "%SONUC%"=="0" (
  echo ==============================================
  echo   KURULUM TAMAMLANAMADI  ^(kod %SONUC%^)
  echo ==============================================
  echo Hata raporu masaustunde: SERVIS-DEFTERI-KURULUM-HATASI.txt
  echo ^(ayrica C:\ServisDefteri\data\kurulum-hata.txt^). Cozum bulamazsan bu dosyayi gonder.
  echo Rapor yoksa ekranda gorunen kirmizi hata mesajini fotografla gonder.
)
pause
exit /b %SONUC%
