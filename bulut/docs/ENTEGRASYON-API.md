# Servis Defteri Entegrasyon API (kısa özet) — çok dükkânlı sürüm

Dış sistemin (ör. muhasebe programı) gönderdiği kaydı, ustanın Servis Defteri'nde açtığı iş emriyle eşleştirir. **Yeni iş emri açmaz.**
Tam belge: `Servis-Defteri-Entegrasyon-API.pdf` (örnek kodlarla) · makine-okunur: `openapi.yaml` · örnekler: `ornekler/`

- `POST https://alan-adin/api/v1/is-emirleri` · `GET /api/v1/saglik` (tüm dükkânlar için tek adres)
- **Her dükkânın kendi API anahtarı vardır; anahtar hangi dükkânın verisine yazılacağını belirler.** Bir dükkânın anahtarı başka dükkânın verisine hiçbir şekilde erişemez.
- Anahtarı yalnızca **yönetici** üretir/yeniler/kapatır: `/yonetici` sayfasında dükkân satırında "🔗 API anahtarı üret". Anahtar **bir kez** gösterilir, sunucuda yalnızca SHA-256 özeti saklanır (kaybolursa yenilenir; eski anahtar o anda geçersiz olur). Biçim: `sk_<dükkân kodu>_<rastgele>`.
- Hiçbir dükkânın anahtarı yoksa API kapalıdır (404). Kapatılan dükkânın anahtarı çalışmaz (401).
- Kimlik: `Authorization: Bearer <API anahtarı>` (ya da `X-API-Key`) · yalnızca HTTPS · isteğe anlamlı bir `User-Agent` ekle (boş/varsayılan kimlikler Cloudflare'de **403** ile kesilebilir)
- Zorunlu alan: `plaka`. İsteğe bağlı: `kayit_no`, `km`, `marka`, `model`, `musteri_ad`, `telefon`, `eposta`, `adres`, `yapilan_islem`, `durum`, `gelis_zamani`, `gidis_zamani`, `not`
- `yapilan_islem`: karşı sistem son karar → mevcut "Yapılan işlem"in yerine yazılır, eski metin nota "Önceki işlem: …" olarak saklanır. "Ne yapılacak?" (geliş nedeni) alanına dokunulmaz.
- Müşteri/araç alanları yalnızca boşsa tamamlanır. `durum` gelirse uygulanır (Tamamlandı → gidiş zamanı yazılır).
- `kayit_no` tekrar koruması **dükkân başınadır**: iki dükkân aynı numarayı bağımsız kullanabilir.
- Eşleşme güvenli değilse (plaka kayıtsız / açık iş emri yok / birden fazla açık / km uyuşmuyor / iş emri çok eski) → `202`, kayıt o dükkânın üst menüsündeki **🔗 Dış sistem** düğmesindeki **Karar bekleyen** sekmesine düşer (başka dükkân görmez). Reddedilen (kabul edilmeyen) istekler aynı sayfada **Reddedilen** sekmesinde görünür; telefon, adres ve e-posta gizlenir.

## .env ayarları (tüm dükkânlar için ortak)
`ENTEGRASYON_KM_TOLERANS=50` · `ENTEGRASYON_GUN_ARALIGI=5` · `ENTEGRASYON_KAYIT_NO_ZORUNLU=0` · `ENTEGRASYON_HTTPS_ZORUNLU=1` · `ENTEGRASYON_YENI_KAYIT=0` (anahtar `.env`'de değil, yönetici panelindedir)

Not: HTTPS denetimi, önündeki tünel/ters vekilin gönderdiği `X-Forwarded-Proto` (Cloudflare'de `CF-Visitor`) başlığına bakar. Uygulamaya doğrudan (vekilsiz) gelen istekte bu başlık olmadığı için `http` olduğu anlaşılamaz ve istek kabul edilir; internete her zaman tünel/vekil üzerinden aç. Hatalı anahtar denemeleri IP başına sınırlanır (10 deneme / 5 dk → 429).

## Test
Başka bir bilgisayardan tek kayıt göndermek için `disaridan_gonder/disaridan_gonder.py` (yalnızca Python gerekir; adresi ve anahtarı sorar). Bu **gerçek** bir istektir: plakanın açık iş emri varsa güncellenir. Dışarıdan 403 gelirse sebep uygulama değil Cloudflare'dir (Security → Events).
