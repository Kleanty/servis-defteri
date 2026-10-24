# PowerShell 5.1+ ornegi
$Base = "https://alanadiniz.com/api/v1"
$Key  = "API_ANAHTARI"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12   # eski sistemlerde TLS 1.2 gerekir

$kayit = @{ kayit_no = "K-10425"; plaka = "35 ABC 123"; km = 120010; yapilan_islem = @("Yağ değişimi", "Yağ filtresi"); durum = "Tamamlandı" }
$govde = [Text.Encoding]::UTF8.GetBytes(($kayit | ConvertTo-Json -Compress))
try {
    $yanit = Invoke-RestMethod -Method Post -Uri "$Base/is-emirleri" -ContentType "application/json; charset=utf-8" `
             -Headers @{ Authorization = "Bearer $Key"; "User-Agent" = "MuhasebeYazilimi/1.0" } -Body $govde
    $yanit | ConvertTo-Json            # eslesti=true -> 200, durum=beklemede -> 202
} catch {
    $kod = [int]$_.Exception.Response.StatusCode
    "HTTP $kod : " + $_.ErrorDetails.Message   # 401/422/409 duzeltmeden tekrar denenmez; 5xx tekrar denenir
}
