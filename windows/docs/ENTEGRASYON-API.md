# Servis Defteri Entegrasyon API (kısa özet)

Dış sistemin (ör. muhasebe programı) gönderdiği kaydı, ustanın Servis Defteri'nde açtığı iş emriyle eşleştirir. **Yeni iş emri açmaz.**
Tam belge: `Servis-Defteri-Entegrasyon-API.pdf` (örnek kodlarla) · makine-okunur: `openapi.yaml` · örnekler: `ornekler/`

- `POST https://alanadiniz.com/api/v1/is-emirleri` · `GET /api/v1/saglik`
- Kimlik: `Authorization: Bearer <ENTEGRASYON_API_ANAHTARI>` · yalnızca HTTPS · isteğe anlamlı bir `User-Agent` ekle (boş/varsayılan kimlikler Cloudflare'de **403** ile kesilebilir)
- Zorunlu alan: `plaka`. İsteğe bağlı: `kayit_no`, `km`, `marka`, `model`, `musteri_ad`, `telefon`, `eposta`, `adres`, `yapilan_islem`, `durum`, `gelis_zamani`, `gidis_zamani`, `not`
- `yapilan_islem`: karşı sistem son karar → mevcut "Yapılan işlem"in yerine yazılır, eski metin nota "Önceki işlem: …" olarak saklanır. "Ne yapılacak?" (geliş nedeni) alanına dokunulmaz.
- Müşteri/araç alanları yalnızca boşsa tamamlanır. `durum` gelirse uygulanır (Tamamlandı → gidiş zamanı yazılır).
- Eşleşme güvenli değilse (plaka kayıtsız / açık iş emri yok / birden fazla açık / km uyuşmuyor / iş emri çok eski) → `202`, kayıt üst menüdeki **🔗 Dış sistem** düğmesindeki **Karar bekleyen** sekmesine düşer. Reddedilen (kabul edilmeyen) istekler aynı sayfada **Reddedilen** sekmesinde görünür; telefon, adres ve e-posta gizlenir.

## .env ayarları
`ENTEGRASYON_API_ANAHTARI` (kurulum otomatik üretir; boşsa API kapalı) · `ENTEGRASYON_KM_TOLERANS=50` · `ENTEGRASYON_GUN_ARALIGI=5` · `ENTEGRASYON_KAYIT_NO_ZORUNLU=0` · `ENTEGRASYON_HTTPS_ZORUNLU=1` · `ENTEGRASYON_YENI_KAYIT=0`

Not: HTTPS denetimi, önündeki tünel/ters vekilin gönderdiği `X-Forwarded-Proto` (Cloudflare'de `CF-Visitor`) başlığına bakar. Uygulamaya doğrudan (vekilsiz, yerel ağdan) gelen istekte bu başlık olmadığı için `http` olduğu anlaşılamaz ve istek kabul edilir; internete her zaman tünel/vekil üzerinden aç.

## Test
`windows\API-DENEME.bat` içindeki internet testi geçiyorsa (6/6) dışarıdan erişim ve güvenlik çalışıyordur. Dışarıdan 403 gelirse sebep uygulama değil Cloudflare'dir (Security → Events).
`windows\API-DENEME.bat` (demo kayıtlarla 17 senaryo, nerede hata olduğunu söyler) · `python scripts\entegrasyon_deneme.py --temizle` demo kayıtları siler.
Başka bir bilgisayardan tek kayıt göndermek için: `DISARIDAN-GONDER\DISARIDAN-GONDER.bat`.
