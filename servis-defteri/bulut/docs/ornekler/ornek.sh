#!/bin/sh
# curl ornegi
BASE="https://alanadiniz.com/api/v1"
KEY="API_ANAHTARI"
curl -sS -X POST "$BASE/is-emirleri" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "User-Agent: MuhasebeYazilimi/1.0" \
  -d '{"kayit_no":"K-10425","plaka":"35 ABC 123","km":120010,"yapilan_islem":["Yağ değişimi","Yağ filtresi"],"durum":"Tamamlandı"}'
