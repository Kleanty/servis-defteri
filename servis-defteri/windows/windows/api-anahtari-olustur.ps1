$ErrorActionPreference = 'Stop'
try {
  $envYol = 'C:\ServisDefteri\.env'
  if (-not (Test-Path $envYol)) { $envYol = Join-Path (Split-Path $PSScriptRoot -Parent) '.env' }
  if (-not (Test-Path $envYol)) { throw ('.env dosyasi bulunamadi: ' + $envYol) }
  $metin = [IO.File]::ReadAllText($envYol)
  if ($metin -match '(?m)^\s*ENTEGRASYON_API_ANAHTARI\s*=\s*\S') {
    Write-Host ''
    Write-Host ' Anahtar ZATEN VAR, degistirilmedi. Gormek icin .env dosyasini Not Defteri ile ac, ENTEGRASYON_API_ANAHTARI satirina bak.' -ForegroundColor Yellow
    exit 0
  }
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create(); $bayt = New-Object byte[] 30; $rng.GetBytes($bayt)
  $anahtar = ([Convert]::ToBase64String($bayt)).Replace('+','A').Replace('/','B').Replace('=','')
  [IO.File]::AppendAllText($envYol, "`r`nENTEGRASYON_API_ANAHTARI=$anahtar`r`n", (New-Object Text.UTF8Encoding($false)))
  Write-Host ''
  Write-Host ' API anahtari olusturuldu ve .env dosyasina yazildi:' -ForegroundColor Green
  Write-Host ''
  Write-Host ('   ' + $anahtar) -ForegroundColor Cyan
  Write-Host ''
  Write-Host ' Bu anahtari bir kagida yaz; yalnizca entegrasyonu kuracak firmaya GUVENLI kanaldan ver.'
  Write-Host ' Simdi windows\YENIDEN-BASLAT.bat dosyasini calistir (yonetici olarak).'
} catch {
  Write-Host ''
  Write-Host (' HATA: ' + $_.Exception.Message) -ForegroundColor Red
  exit 1
}
