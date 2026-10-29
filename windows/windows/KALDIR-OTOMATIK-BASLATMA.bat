@echo off
fltmc >nul 2>&1
if errorlevel 1 (
  echo Bu dosyayi YONETICI olarak calistir: sag tikla - "Yonetici olarak calistir".
  pause
  exit /b 1
)
schtasks /end /tn "ServisDefteri" >nul 2>&1
schtasks /delete /tn "ServisDefteri" /f
schtasks /delete /tn "ServisDefteri-Yedek" /f
schtasks /delete /tn "ServisDefteri-YedekKontrol" /f
echo Otomatik baslatma ve otomatik yedek gorevleri kaldirildi (verilerin silinmedi).
pause
