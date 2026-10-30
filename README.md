![Empires & Allies](templates/img/logo.png "Empires & Allies logo")

# Raise the Empires — Türkçe

Zynga'nın 2013'te kapanan Facebook oyunu **Empires & Allies**'ı bilgisayarında oynamanı sağlayan
[Raise the Empires](https://github.com/AcidCaos/raisetheempires) projesinin **Türkçe ve geliştirilmiş** sürümü.

Asıl proje Raise the Empires ekibine aittir; bu repo onun üzerine kuruludur ve aynı **GPL-3.0** lisansıyla
dağıtılır. Orijinal açıklama: [README.en.md](README.en.md).

## Bu sürümde neler var?

**Türkçe oyun**
- Menüler, eşyalar, binalar, birimler, görevler, kampanya, karakter konuşmaları, mini diziler ve duyurular
  Türkçe — oyunda görülen metinlerin ~%99'u (25.000'den fazla metin).
- Oyunun yazı tiplerinde olmayan **ğ, ı, İ, ş** harfleri yazı tiplerine eklendi; diyalog pencerelerindeki
  yazı tiplerine de Türkçe harfler eklendi.

**Düzeltmeler**
- 66. seviyeden sonra görev ödülüyle seviye atlarken oluşan çökme.
- Kayıt dosyasının yedeklerle şişmesi (yedekler artık ayrı `backups.db` dosyasında; kayıt 2 MB'tan 0,3 MB'a indi).
- Sayfayı yenileyince kaybolan **kilit açmaları** (birim, eşya, kaynak, araştırma binası) ve parayla yapılan
  işlemler (görev adımı ödeme, ödül satın alma, tam iyileştirme, görev yeniden başlatma, toplu hasat…).
- Yarıda kalan isteklerde kaydın bozulması (hata olursa kayıt isteğin öncesine geri alınır).
- Ücretsiz eşyalarda ve eksik nesnelerde çökmeler, modların hiç yüklenmemesi, siteler arası istek koruması.

**Yeni özellikler**
- **Mini diziler** (çok bölümlü özel görev dizileri): sunucuda hiç yoktu, sıfırdan yazıldı. Oyun dosyaları
  eksiksiz olan 7 dizi oynanabilir. Oyunun kendi kodundaki bir hata (dizi binasının yerleştirilememesi)
  sunucu tarafından düzeltilerek gönderiliyor (`client_patches.py`).
- **Mega diziler** (deneysel): MS02, MS03, MS04.
- **Parça etkinlikleri** (deneysel): Yanardağ, Göktaşı, Derin Deniz Sondajı, Kasırga ve Nükleer Santral
  sırayla gelir. Her biri oyuncuya özel süreyle başlar; her gün bir parça kendiliğinden gelir, binayı ne
  kadar erken çalıştırırsan ödül o kadar büyük olur, süre dolarsa teselli ödülü verilir (`event_buildings.py`).
  Eksik ekran ve resimlerin yerine var olanlar kullanılır.
- **Titan Laboratuvarı** (deneysel): parasıyla ya da öncekini toplayarak açılan parçalar kaydedilir; Titan
  savaşlarını sunucu da yürütür, kazanınca parçası verilir (`titan_lab.py`).
- **Hazine Kasası** (deneysel): 26. seviyede görevle gelir; anahtarla ya da nakitle dört kasa açılır, anahtar
  bitince 24 saatte bir bedava anahtar gelir. Asıl ödül listeleri kayıp olduğundan oyunun slot makinesi
  ödüllerinden kuruldu (`treasure_vault.py`).
- **Slot makinesi** (deneysel): boks eldiveni düğmesiyle açılan yabancılar çubuğundaki jetondan girilir; jetonla
  ya da nakitle çevrilir, ödüller oyunun kendi listesinden gelir (`slot_machine.py`). Çubuktaki bayrağa basma:
  PvP'den çıkma penceresinin dosyası kayıp.
- **Ödül Merkezi** (deneysel): 20. seviyede görevle gelir; enerjiyle bir saatliğine çalıştırılır, açıkken
  en çok 10 seviye düşük oyunculara karşı kazanılan savaşlar Özgürlük Tahvili verir (`bounty_center.py`).

## Kurulum

1. Resmi Raise the Empires kurulumunu yap (oyunun Flash'lı tarayıcısı ve klasörleri onunla gelir):
   [son sürüm](https://github.com/AcidCaos/raisetheempires/releases/latest).
2. Python 3.12 kur, bu repoyu indir ve bağımlılıkları yükle:
   ```
   pip install -r requirements.txt
   ```
3. Repo klasöründe `RaiseTheEmpires.ini` dosyası oluştur (resmi kurulumdakini örnek alabilirsin):
   ```
   [InstallFolders]
   InstallPath=<bu repo klasörü>
   MyGamesPath=<kayıtların duracağı klasör>
   ```
4. Türkçe yamayı kur:
   ```
   python turkce/kur.py
   ```
5. Sunucuyu başlat ve oyunu Flash'lı tarayıcıda `http://127.0.0.1:5005/` adresinden aç:
   ```
   python empires-server.py
   ```

Windows 11'de oyun gri ekranda kalırsa resmi kurulumdaki Chromium'u `--no-sandbox` ile başlatın.
`turkce/baslatici/` klasöründe yedek alıp sunucuyu ve oyunu tek tıkla açan örnek bir başlatıcı var.

## Çeviri araçları (`turkce/araclar/`)

| Araç | Ne yapar |
|---|---|
| `ceviri.py cikar / kontrol / uret` | Çevrilecek metinleri çıkarır, çevirileri denetler (yer tutucular, harfler), Türkçe `en_US.xml` üretir |
| `ceviri/parca_*.json` | Bütün çeviriler (İngilizce → Türkçe) |
| `yazi_tipi_yamala.py`, `yazi_tipi_tamamla.py` | Oyunun SWF yazı tiplerine Türkçe harfleri ekler |
| `abc.py` | Oyunun ActionScript kodunu okumak için küçük bir çözücü (sınıflar, metotlar, çağrılar) |

Çeviride hata görürsen ilgili `ceviri/parca_*.json` dosyasını düzeltip `uret` ile yeniden üretebilirsin.

## Lisans

GPL-3.0 — bkz. [LICENSE](LICENSE). Empires & Allies, Zynga'nın markasıdır; bu proje oyunu korumak amacıyla
gönüllüler tarafından yapılmıştır.
