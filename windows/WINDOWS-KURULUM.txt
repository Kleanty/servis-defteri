# Windows bilgisayara kurulum

Dükkandaki Windows PC uygulamanın sunucusu olur, etiket yazıcısı o PC'ye USB ile takılır. Hosting kiralamazsın; **sadece alan adı** (domain) alırsın. Kurulum yaklaşık 30–40 dakika sürer.

> **Durum:** Raspberry Pi + Xprinter XP-470B gerçek donanımda test edildi. Windows yazdırma yolu ve kurulum betikleri otomatik testlerle (sahte Windows yazıcısı) doğrulandı; **Windows'ta ilk gerçek yazdırmayı sen 6. adımdaki `ETIKET-DENEME.bat` ile doğrulamalısın.**

## Neye ihtiyacın var
- Windows 10 veya 11 bilgisayar. Dükkan açıkken **sürekli açık** kalacak (kapalıysa sistem de kapalıdır).
- Internet bağlantısı, bir alan adı (ör. `alanadiniz.com`) ve ücretsiz bir Cloudflare hesabı.
- Xprinter XP-470B (veya başka TSPL etiket yazıcısı) ve 58×40 mm etiket rulosu.

# DUKKAN BILGISAYARINA TEK TIKLA KURULUM (en kolay yol)
1. USB'deki zip'i bilgisayara at ve **Tumunu ayikla** (Extract all).
2. Cikan klasordeki **SERVIS-DEFTERI-KUR.bat** dosyasina cift tikla, "Yonetici izni" sorarsa **Evet** de.
3. Bekle (internet gerekir, 5-10 dk). Python yoksa kendisi kurar; dosyalari C:\ServisDefteri'ne koyar; paketleri kurar; bilgisayar her acildiginda sistemin kendiliginden baslamasini ayarlar; etiket yazicisini arar ve deneme etiketi basar; masaustune "Servis Defteri" kisayolu koyar; ilk giris sifresini ekrana yazar.
4. Masaustundeki **Servis Defteri** kisayolu panele gider. Ilk sifreyle girince `windows\SIFRE-DEGISTIR.bat` ile degistir.
Sonradan guncelleme: yeni zip'i ayikla, yine SERVIS-DEFTERI-KUR.bat calistir. Kayitlar (data) ve .env ayarlarin silinmez.
Ayarlar> Sistem> Guc> Uyku: "Hicbir zaman" secmeyi unutma. Yazici surucusu kurulu degilse asagidaki 4. adima bak.

(Asagidaki adimlar elle kurulum icindir; SERVIS-DEFTERI-KUR.bat bunlarin hepsini kendisi yapar.)

## Hizli deneme (kendi bilgisayarinda, domain olmadan)
Isletme bilgilerini (ad, telefon, adres) `.env` dosyasina yaz; kurulum `.env.example`'dan bir `.env` olusturur. Domain almadan once denemek icin: Python kur (asagidaki 1. adim) -> zip'i C:\ServisDefteri'ne cikar -> `windows\1-KUR.bat` (Not Defteri acilirsa kapat) -> `windows\2-BASLAT.bat` -> tarayicida http://localhost:5000 (vitrin) ve http://localhost:5000/login (panel). Ilk sifre: data\ILK_SIFRE.txt. PUBLIC_BASE_URL bos kalsin; domain alinca doldurulur.

## 1. Python kur
python.org/downloads → **Python 3.12** indir. Kurulumda ilk ekranda en alttaki **"Add python.exe to PATH"** kutusunu işaretle, sonra "Install Now".

## 2. Dosyaları yerleştir
Zip'i `C:\ServisDefteri` klasörüne çıkar (Masaüstü, İndirilenler, OneDrive içine **koyma**; klasör yolunda boşluk ve Türkçe karakter olmasın). `C:\ServisDefteri\windows` klasörü görünmeli.

## 3. Kur
`windows\1-KUR.bat` dosyasına çift tıkla. Paketleri indirir, `.env` ayar dosyasını oluşturur ve Not Defteri'nde açar. Şunları doldur, kaydet, kapat:
- `ISLETME_ADI`, `ISLETME_TEL`, `ISLETME_ADRES`, `ISLETME_ACIKLAMA`
- `PUBLIC_BASE_URL` şimdilik **boş kalsın**; site alan adında (ör. `https://alanadiniz.com`) açıldıktan sonra yazılır (8. adım)
- `ETIKET_BASLIK` (etikette yazacak ad, en fazla 18 karakter)

## 4. Yazıcıyı tak ve sürücüsünü kur
1. XP-470B'yi USB ile tak, aç, rulo tak.
2. Üreticinin Windows sürücüsünü kur; yazıcı **Ayarlar → Yazıcılar ve tarayıcılar** içinde görünmeli. Sürücü bulamazsan Windows'un genel sürücüsü de yeter, çünkü uygulama yazıcıya ham veri gönderir:
   *Yazıcı ekle → "İstediğim yazıcı listede yok" → "Yerel yazıcı ekle" → Bağlantı noktası: `USB001` (varsa "Virtual printer port for USB") → Üretici: **Generic** → **Generic / Text Only** → ad olarak `Etiket` yaz.*
3. Windows'un "Varsayılan yazıcı" ayarına dokunma; uygulama etiketi asla varsayılan (kâğıt) yazıcıya göndermez.

## 5. Yazıcıyı uygulamaya tanıt
`windows\YAZICILARI-LISTELE.bat` çalıştır. Etiket yazıcın `>>` işaretiyle görünüyorsa tamam. Görünmüyorsa adının bir parçasını `.env` içine yaz: `ETIKET_YAZICI_ADI=XP-470B`

## 6. Etiket denemesi
`windows\ETIKET-DENEME.bat` → yazıcıdan örnek etiket çıkmalı. Çıkmazsa aşağıdaki "Sorun giderme" tablosuna bak. Etiket kaymışsa `.env` içinde `ETIKET_X_OFFSET` / `ETIKET_Y_OFFSET` ayarla (8 nokta = 1 mm, ayrıntı: docs\YAZICI.md).

## 7. Uygulamayı başlat
- Deneme: `windows\2-BASLAT.bat` → tarayıcıda `http://localhost:5000`. İlk giriş şifresi `C:\ServisDefteri\data\ILK_SIFRE.txt` içinde. Girince hemen değiştir: `windows\SIFRE-DEGISTIR.bat`.
- Kalıcı: `windows\3-OTOMATIK-BASLAT-KUR.bat` dosyasına **sağ tık → Yönetici olarak çalıştır**. Uygulama bilgisayar her açıldığında (kimse oturum açmasa bile) kendiliğinden başlar, çökerse yeniden denenir. Gece 02:00'de de yedek alınır. (Önce `2-BASLAT.bat` penceresini kapat.)

## 8. Alan adını bağla (Cloudflare Tunnel)
Router'da port açmak gerekmez, HTTPS otomatik gelir.
1. cloudflare.com → ücretsiz hesap → **Add a site** → alan adını ekle. Alan adını aldığın firmada **nameserver**'ları Cloudflare'in verdiği ikisiyle değiştir (yayılması birkaç saat sürebilir).
2. Cloudflare panelinde **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**. Windows'u seç; gösterilen kurulum komutunu **yönetici PowerShell**'e yapıştır (cloudflared'ı Windows servisi olarak kurar).
3. Tünelde **Public hostname** ekle: alan adın → Servis: **HTTP** → `localhost:5000`.
4. **Site alan adında açıldıktan sonra** `.env` içine `PUBLIC_BASE_URL=https://alanadiniz.com` yaz ve `windows\YENIDEN-BASLAT.bat`'ı yönetici olarak çalıştır. Önce yazarsan o arada basılan etiketlerin QR kodu açılmayan bir adrese gider.

(Cloudflare arayüzündeki menü adları zamanla değişebilir; "Tunnel" ve "Public hostname" kelimelerini ara.)

## 9. Bilgisayar ayarları (önemli)
- **Güç → Uyku: "Hiçbir zaman"** (Ayarlar → Sistem → Güç). Ekran kapanabilir, bilgisayar uyumasın.
- **Windows Update:** Etkin saatleri dükkan açık saatlerine ayarla; yeniden başlatma gece olsun. Uygulama açılışta kendiliğinden döner.
- **Saat dilimi:** "Türkiye (UTC+03:00)" ve saat otomatik. Kayıtlardaki saatler PC saatini kullanır.
- **Elektrik kesintisi:** Mümkünse küçük bir UPS tak; BIOS'ta "AC Power Loss → Power On" seçeneği varsa aç.
- **Güvenlik:** Bilgisayarı kullanıcı şifresi/kilit ekranıyla koru, Windows Defender açık kalsın. Veri `C:\ServisDefteri\data` içindedir.

## 10. Yedek
- Otomatik yedek her gece 02:00'de ve her açılışta alınır: `data\yedekler\` (30 gün saklanır). Elle: `windows\YEDEK-AL.bat`.
- **USB bellek yedeği (otomatik):** Belleğin adını (birim etiketi) `servisyedek` yap (Bu Bilgisayar → belleğe sağ tık → Yeniden adlandır; büyük/küçük harf önemsiz). Bellek takılınca en geç 15 dakika içinde yedek `ServisDefteriYedek\` klasörüne kopyalanır; takılı kalırsa 6 saatte bir tazelenir, gece 02:00 yedeği de oraya gider. Takılı değilse yedek yerelde alınır, bellek takılınca otomatik tamamlanır. Başka bir ad istersen `.env` içine `USB_YEDEK_ADI=...` yaz.
- **Google Drive yedeği (online):** Bir kez `windows\DRIVE-YEDEK-KUR.bat` dosyasına çift tıkla (yönetici izni ister). Tarayıcı açılır, yedeğin gideceği Google hesabıyla giriş yapıp "İzin ver" de. Sonrası otomatik: Drive'da `ServisDefteriYedek` klasörüne yalnızca yeni yedekler yüklenir (30 günden eskiler silinir); internet yoksa sonra yeniden denenir. İzin yalnızca bu programın yüklediği dosyalarla sınırlıdır, Drive'daki diğer dosyalarına erişmez. Hata olursa `data\yedek.log` dosyasına bakılır.
- Veritabanı dışında bir şey (ör. şifre dosyası) USB'ye veya Drive'a gitmez.
- **Yedeklerin bilgisayarla aynı diskte kalması yetmez.** USB/Drive yoksa `.env` içine `YEDEK_KLASORU=D:\ServisYedek` yaz (ikinci disk ya da OneDrive klasörü olabilir); her yedek oraya da kopyalanır. Panelde "Son yedek" satırı yedeğin güncel olup olmadığını gösterir.
- **Geri yükleme:** `windows\YEDEKTEN-GERI-YUKLE.bat` (yönetici izni ister): bu bilgisayardaki, USB'deki ya da Drive'daki yedekler listelenir, birini seç, EVET yaz. Mevcut kayıtlar silinmez, `data\servis_ONCEKI_<tarih>.db` olarak saklanır; uygulama kendiliğinden durup yeniden başlar.

## 11. Güncelleme
Uygulamayı durdur, yeni sürümün dosyalarını `C:\ServisDefteri` üzerine kopyala (**`data` klasörüne ve `.env` dosyasına dokunma**), `windows\1-KUR.bat` çalıştır (yeni paketleri kurar, `.env`'i değiştirmez), sonra `windows\YENIDEN-BASLAT.bat`.

## 12. Muhasebe / dış sistem entegrasyonu (isteğe bağlı)
Muhasebe programı kayıt açınca Servis Defteri'ne haber verebilir: plakanın açık iş emrine yapılan işlem, durum ve notlar işlenir (yeni iş emri açılmaz, etiket basılmaz). Emin olunamayan kayıtlar üst menüdeki **🔗 Eşleşmeyen** rozetinde bekler.
- Kurulum API anahtarını kendisi üretir (`.env` içinde `ENTEGRASYON_API_ANAHTARI`, ayrıca `data\ENTEGRASYON-ANAHTARI.txt`). Anahtar boşsa API kapalıdır.
- Adres: `https://alan-adin/api/v1/is-emirleri` (yalnızca HTTPS; alan adı bağlandıktan sonra, bkz. adım 8).
- Entegrasyon firmasına verilecek belgeler: `docs\Servis-Defteri-Entegrasyon-API.pdf`, `docs\openapi.yaml`, `docs\ornekler\`. Yönetici rehberi (firmaya verilmez): `docs\YONETIM-REHBERI.pdf`.
- Denemek için: `windows\API-DENEME.bat`. Başka bir bilgisayardan tek kayıt göndermek için: `DISARIDAN-GONDER\DISARIDAN-GONDER.bat`.

## Kullanışlı dosyalar (`windows\`)
| Dosya | Ne yapar |
|---|---|
| `1-KUR.bat` | Kurulum (güvenle tekrar çalıştırılabilir) |
| `2-BASLAT.bat` | Pencerede çalıştırır (deneme için) |
| `3-OTOMATIK-BASLAT-KUR.bat` | Bilgisayar açılınca otomatik başlatma + gece yedeği (yönetici) |
| `YENIDEN-BASLAT.bat`, `DURDUR.bat` | Uygulamayı yeniden başlatır / durdurur (yönetici) |
| `YEDEK-AL.bat`, `SIFRE-DEGISTIR.bat` | Anlık yedek, yönetici şifresini değiştir |
| `DRIVE-YEDEK-KUR.bat`, `YEDEKTEN-GERI-YUKLE.bat` | Google Drive yedeğini kur (bir kez), yedekten geri yükle |
| `YAZICILARI-LISTELE.bat`, `ETIKET-DENEME.bat` | Yazıcı adlarını göster, örnek etiket bas |
| `API-ANAHTARI-OLUSTUR.bat`, `API-DENEME.bat` | Entegrasyon API anahtarı üret (varsa değiştirmez), API'yi demo kayıtlarla dene |
| `KALDIR-OTOMATIK-BASLATMA.bat` | Otomatik başlatma ve yedek görevlerini kaldırır (veri silinmez) |

## Sorun giderme
| Belirti | Çözüm |
|---|---|
| `1-KUR.bat`: "Python bulunamadı" | Python'u kurarken "Add python.exe to PATH" işaretli olmalı; işaretlemediysen Python'u kaldırıp yeniden kur. |
| Pakette hata / internet | İnternet var mı kontrol et, `1-KUR.bat`'ı tekrar çalıştır. |
| Etiket çıkmıyor, "yazıcı bulunamadı" | `YAZICILARI-LISTELE.bat` → adı `.env` içine `ETIKET_YAZICI_ADI` olarak yaz. |
| "Yazıcı çevrimdışı görünüyor" | USB kablosu, yazıcının açık olması. Windows'ta yazıcıya sağ tık → "Yazdırma kuyruğunu aç" → Yazıcı menüsünde **"Yazıcıyı çevrimdışı kullan"** işaretliyse kaldır. |
| İş kuyrukta takılı kalıyor | "Print Spooler" hizmeti çalışmalı (Hizmetler). Kuyruktaki işleri iptal et, yazıcıyı kapat-aç. |
| Etiket boş / saçma karakter çıkıyor | Yazıcı TSPL konuşmuyor olabilir; yazıcı komut dilini TSPL yap (üretici aracı). |
| Etiket kayık / ters | `.env`: `ETIKET_X_OFFSET`, `ETIKET_Y_OFFSET`, `ETIKET_YON` (0 veya 1). |
| Siteye dışarıdan girilemiyor | Tünel servisi çalışıyor mu (Cloudflare panelinde "Healthy")? Uygulama `localhost:5000`'de açılıyor mu? |
| Bilgisayar yeniden başlayınca site gelmiyor | `3-OTOMATIK-BASLAT-KUR.bat` yönetici olarak çalıştırıldı mı? Görev Zamanlayıcı'da "ServisDefteri" görevi var mı? |
| Hata ayrıntısı | `data\uygulama.log` ve `data\sunucu.log` dosyalarına bak. |
| Yerel ağdan (dükkan Wi-Fi'si) telefonla bağlanmak | `.env`: `DINLE_ADRES=0.0.0.0`, uygulamayı yeniden başlat; telefonda `http://BILGISAYAR-IP:5000`. Güvenlik duvarı izin sorarsa "Özel ağlar"a izin ver. |


KALDIRMA (kurulumun tersi)
------------------------------------------------------------
KALDIR.bat dosyasina cift tikla (yonetici izni sorarsa Evet). Sunlari yapar:
  - "ServisDefteri", "ServisDefteri-Yedek" ve "ServisDefteri-YedekKontrol" Windows gorevlerini siler, calisan uygulamayi durdurur
  - masaustundeki "Servis Defteri" kisayollarini siler
  - kayitlarin ne olacagini SORAR: [1] saklayip C:\ServisDefteriYedek-<tarih> klasorune kopyala (onerilen),
    [2] hepsini sil (geri donusu yok), [3] sadece durdur, klasore dokunma
  - C:\ServisDefteri klasorunu siler
  - Python'u yalnizca kurulum yukledi ise ve sen "e" dersen kaldirir
Dokunmaz: Cloudflare tuneli, yazici surucusu, .env icindeki dis yedek klasoru.
Kaldirma kaydi: %TEMP%\servis-defteri-kaldir.log
