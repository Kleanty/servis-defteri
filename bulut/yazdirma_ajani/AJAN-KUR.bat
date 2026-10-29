@echo off
rem Servis Defteri yazdirma ajani kurulumu. Yonetici olarak calistir.
rem Hata olursa: ekranda adim + olasi neden yazar; C:\ServisAjan\kurulum-hata.txt ve masaustune SERVIS-DEFTERI-KURULUM-HATASI.txt olusur.
echo "%~dp0" | findstr /i /c:"\AppData\Local\Temp" >nul
if not errorlevel 1 (
  echo UYARI: Bu dosya zip'in icinden calistiriliyor gibi gorunuyor.
  echo Once zip'e sag tikla - "Tumunu ayikla" de, cikan KLASORUN icinden tekrar calistir.
  pause
  exit /b 1
)
fltmc >nul 2>&1
if errorlevel 1 (
  echo Bu dosyayi YONETICI olarak calistir: dosyaya sag tikla - "Yonetici olarak calistir".
  pause
  exit /b 1
)
if not exist "%~dp0ajan-kur.ps1" (
  echo HATA: ajan-kur.ps1 bulunamadi. Klasor eksik kopyalanmis; "yazdirma_ajani" klasorunun tamamini kopyala.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ajan-kur.ps1"
set "SONUC=%errorlevel%"
if not "%SONUC%"=="0" (
  echo.
  echo ==============================================
  echo   KURULUM TAMAMLANAMADI  ^(kod %SONUC%^)
  echo ==============================================
  echo Hata raporu masaustunde: SERVIS-DEFTERI-KURULUM-HATASI.txt  ^(ayrica C:\ServisAjan\kurulum-hata.txt^).
  echo Cozum bulamazsan bu dosyayi gonder; rapor yoksa kirmizi hata mesajini fotografla gonder.
)
pause
exit /b %SONUC%
