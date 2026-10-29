# Çok dükkânlı sürüm (bulut) — kurulum

**Ne için?** Tek bir internete açık Linux sunucuda birden fazla dükkânın kullanması. Her dükkân kendi **kullanıcı adı + şifresiyle** girer, kendi verisini görür; başkasının verisine erişemez. Etiket, dükkândaki yazıcıya **telefondan Bluetooth ile** ya da **dükkân bilgisayarındaki USB yazıcıdan** (küçük bir "yazdırma ajanı" ile) basılır; sunucu yazıcıya doğrudan bağlanmaz.

## Nasıl çalışır?
- **Veri ayrımı:** her dükkânın veritabanı ayrı dosyadır: `data/dukkanlar/<no>/servis.db`. Hesap listesi `data/yonetim.db` içindedir.
- **Hesapları yalnızca yönetici (sen) açar:** `https://alanadin/yonetici/giris`. Dükkân adı + kullanıcı adı girersin, sistem **geçici şifre** üretir (bir kez görünür). Dükkân ilk girişte kendi şifresini seçer.
- **Şifre unutulursa:** yönetici sayfasında "Şifre sıfırla" → yeni geçici şifre. E-posta gönderimi yoktur.
- **Dükkânı kapatma:** "Kapat" girişi ve QR sayfalarını durdurur, veri silinmez.
- **QR kodu:** her aracın QR adresi `https://alanadin/arac/<rastgele kod>`; kodun ilk 4 harfi dükkânı belirler, geri kalanı tahmin edilemez. Adreste dükkân adı görünmez.
- **Yönetici şifresi** dükkân şifresinden ayrıdır (`data/.password_hash`; `scripts/sifre_degistir.py` ile değişir).

## 1. Kurulum (Debian / Ubuntu / Raspberry Pi)
```bash
sudo apt install -y python3-venv
cd ~/ServisDefteri          # zip'i çıkardığın klasör
bash scripts/kurulum.sh
nano .env                   # yalnızca PUBLIC_BASE_URL (alan adın)
```
Betik sudo kullanmaz; sonda çalıştırman gereken komutları yazar (servis, yönetici şifresi, günlük yedek).

## 2. Servis (systemd)
```bash
sudo cp deploy/servis-defteri.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now servis-defteri
```
Uygulama `127.0.0.1:5000` üzerinde çalışır; internete **Cloudflare Tunnel** ile açılır (`DOMAIN-BAGLAMA.txt`). HTTPS şarttır: hem güvenlik hem telefondan Bluetooth yazdırma için.

## 3. Yönetici şifresi ve ilk dükkân
```bash
sudo journalctl -u servis-defteri -n 30 --no-pager | grep -A1 "İLK KURULUM"      # ya da: cat data/ILK_SIFRE.txt
venv/bin/python scripts/sifre_degistir.py && sudo systemctl restart servis-defteri
```
Sonra `https://alanadin/yonetici/giris` → **Yeni dükkân** → kullanıcı adı ve geçici şifreyi dükkâna ilet. Dükkân `https://alanadin/login` adresinden girer.

**Cihaz adı:** Giriş yaptıktan sonra her telefon/bilgisayar bir kez ad ister (ör. "Usta telefonu"); kim neyi yaptığı **İstatistik → Hareketler** sayfasında 180 gün görünür. Kayıtta müşteri adı/telefonu tutulmaz. Ad sonradan aynı sayfadan değiştirilebilir.

## 4. Yedek ve geri yükleme
- **Otomatik:** `kurulum.sh` sonunda yazdırılan cron satırı her gece 02:00'de `scripts/backup.py` çalıştırır: her dükkân kendi klasörüne (`data/dukkanlar/<no>/yedekler/`) yedeklenir, ayrıca hesap listesi (`data/yonetim_yedek/`). Bütünlük denetimi yapılır, 30 günden eski yedekler silinir. İsteğe bağlı `RCLONE_REMOTE` ile sunucu dışına bulut kopyası.
- **Dükkânın kendi yedeği:** panelde **📥 Veri, yedek, şifre → 💾 Tüm veriyi yedek olarak indir** (tek `.db` dosyası).
- **Geri yükleme (yalnızca yönetici):**
```bash
sudo systemctl stop servis-defteri
venv/bin/python scripts/geri_yukle.py ahmet-oto                       # o dükkânın yedeklerini listeler
venv/bin/python scripts/geri_yukle.py ahmet-oto data/dukkanlar/1/yedekler/servis_YYYYMMDD_HHMMSS.db
sudo systemctl start servis-defteri
```
Yedek önce denetlenir; mevcut veri silinmez, `geri_yukleme_oncesi_*.db` olarak saklanır.
- Hesap listesini (`yonetim.db`) kaybedersen dükkânlar giremez; `data/yonetim_yedek/` içindeki en yeni dosyayı `data/yonetim.db` olarak kopyala.

## 5. Güncelleme
Yeni sürümün dosyalarını klasörün üzerine kopyala (**`data/` ve `.env`'e dokunma**) → `venv/bin/pip install -r requirements.txt` → `sudo systemctl restart servis-defteri`. Her dükkânın veritabanı açılışta otomatik güncellenir. Açılışta `data/` izinleri de otomatik sıkılaştırılır (klasörler 0700, dosyalar 0600). Bir dükkânın veritabanı bozuksa o dükkân 503 verir, diğerleri çalışmaya devam eder; yönetici sayfasında "veritabanı açılamadı" etiketi görünür ve `geri_yukle.py` ile geri yüklenir.

## 6. Demo
`venv/bin/python scripts/demo_veri.py` — `demo` adlı bir dükkân açar (şifre `Demo-Sifre-12345`) ve sahte kayıt ekler. Yalnızca deneme kurulumunda kullan.

## 7. Dış sistem API'si (isteğe bağlı, dükkân başına)
Muhasebe programı bir dükkânın açık iş emrine işlem/durum/not ekleyebilir. Anahtarı yalnızca yönetici verir: `/yonetici` → dükkân satırında **🔗 API anahtarı üret** (bir kez gösterilir; yenilenince eskisi geçersiz; "API'yi kapat" ile kapanır). Adres hepsi için aynı: `https://alan-adin/api/v1/is-emirleri`; anahtar hangi dükkân olduğunu belirler, dükkânlar birbirinin verisine erişemez. Belgeler: `docs/Servis-Defteri-Entegrasyon-API.pdf`, `docs/openapi.yaml`, `docs/ornekler/`, kısa özet `docs/ENTEGRASYON-API.md`. Ayarlar `.env.example` sonundadır. Anahtarı firmaya güvenli kanaldan ver.

## 8. Dükkân bilgisayarındaki USB yazıcı (yazdırma ajanı, isteğe bağlı)
Dükkânda yazıcı bilgisayara USB ile takılıysa (Bluetooth yok) etiketi şöyle basarsın: dükkân bilgisayarında küçük bir **ajan** çalışır; sunucuya kendisi (dışarı doğru, HTTPS) bağlanıp "basılacak etiket var mı?" diye sorar, varsa yazıcıya gönderir. **Modemden port açmak ya da VPN gerekmez.** Bluetooth yolu aynen durur; ikisi birlikte kullanılabilir.
1. **Yönetici:** `/yonetici` → dükkân satırında **🖨️ Ajan anahtarı üret**. Anahtar (`ya_…`) yalnızca bir kez görünür; dükkâna güvenli kanaldan ilet. Yenilersen eskisi çalışmaz; **Ajanı kapat** ile iptal edilir.
2. **Dükkân bilgisayarı (Windows):** `yazdirma_ajani` klasörünü bilgisayara kopyala, `AJAN-KUR.bat` dosyasına sağ tık → **Yönetici olarak çalıştır**. Sihirbaz Python'u (yoksa) kurar, sunucu adresini ve ajan anahtarını sorar, bağlantıyı dener, yazıcıyı arar, deneme etiketi basabilir ve ajanı bilgisayar açılınca otomatik başlayacak şekilde ayarlar. Sorun olursa `AJAN-DENEME.bat`.
3. **Kullanım:** Araç → **Etiket** ekranında **🖨️ Dükkân bilgisayarından bas**; birkaç saniyede etiket bilgisayardaki yazıcıdan çıkar. Ekran "basıldı" ya da hatayı (yazıcı çevrimdışı vb.) gösterir.

Bilmen gerekenler:
- Bilgisayar kapalıysa ya da ajan çalışmıyorsa etiket 30 dakika kuyrukta bekler; açılınca basılır, süre dolarsa "Süresi doldu" olur ve basılmaz (eski etiketler yığılıp birden çıkmasın).
- Ajan etiketi aldıktan sonra yanıt vermezse (bilgisayar o anda kapandı vb.) o iş **tekrar basılmaz**; ekran "çıkmış olabilir, kontrol et" der.
- Yazıcı adı otomatik bulunur (XP-470, Xprinter, "Etiket", "Label" geçen adlar); farklıysa `C:\ServisAjan\ajan.env` içine `ETIKET_YAZICI_ADI=` ekle. Kayıt dosyası: `C:\ServisAjan\ajan.log`.
- Linux/Raspberry bilgisayarda: `yazdirma_ajani` klasöründe `python3 -m venv venv && venv/bin/pip install -r requirements.txt`, `ajan.env` dosyasını doldur (örnek: `ajan.env.example`), `servis-ajan.service.example` ile systemd'ye ekle.
- Ajanın yazıcı tarafı Windows/Linux paketlerindeki `etiket_yazici.py` ile aynıdır. Gerçek yazıcıyla ilk deneme `AJAN-DENEME.bat` ile yapılmalıdır.

## Kurulum hata verirse
`scripts/kurulum.sh` her adımı `data/kurulum.log` dosyasına, pip çıktısını `data/kurulum-pip.log` dosyasına yazar. Bir adım başarısız olursa ekranda **hangi adımda** takıldığı ve olası neden/çözüm yazılır; ayrıca **`data/kurulum-hata.txt`** raporu oluşur: adım, betikte satır/komut, sistem (dağıtım, Python, venv, disk, bellek, proxy), pypi.org erişimi ve kaydın sonu. Çözemezsen bu dosyayı olduğu gibi gönder: `cat data/kurulum-hata.txt`. Başarılı bir kurulumda eski rapor silinir.
Ajan kurulumunda (Windows) aynı rapor masaüstünde `SERVIS-DEFTERI-KURULUM-HATASI.txt` ve `C:\ServisAjan\kurulum-hata.txt` olarak oluşur.

## Sınırlar (bilerek)
- E-posta ile şifre sıfırlama, kendi kendine kayıt, dükkân başına özel vitrin/logo yoktur. Ana sayfa (`/`) tek bir ortak tanıtım sayfasıdır; iletişim e-postası `.env` içindeki `VITRIN_EPOSTA` ile değişir, `-` yazarsan iletişim bölümü gizlenir.
- Tek sunucu, tek SQLite; onlarca küçük dükkân için uygundur. Çok yüksek kullanımda ayrı mimari gerekir.
