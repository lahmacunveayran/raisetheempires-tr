# Birinci kalite denetimi — 31 Ekim 2026

Proje sahibinin isteği: projeyi kitap gibi bölümlere ayırıp her bölümü bağımsız bir denetçiye inceletmek. Bu ilk tur
iki bölümü kapsar; öteki dört bölüm sonraki turlara kaldı (Bölüm 6).

- **Bölüm 1 — Sunucu çekirdeği ve kayıt** (`empires-server.py`, `save_engine.py`, `save_migration.py`,
  `state_machine.py`, `logger.py`, `init_settings.py`). Tam rapor: [`denetim/cekirdek.md`](denetim/cekirdek.md).
- **Bölüm 2 — Savaş ve PvP** (`battle_engine.py`, `bot_empires.py`, `bounty_center.py`, `titan_lab.py` ve sunucudaki
  savaş çağrıları). Tam rapor: [`denetim/savas.md`](denetim/savas.md).

Denetlenen kod: dal `denetim-1` @ `a4de86e` (GitHub `main` ile aynı). Bu belge iki raporu özetler, bulguları birleştirir
ve önceliklendirir. Raporların kendisi denetçilerin yazdığı gibi, kelimesi kelimesine durur.

## 0. Yönetici özeti (proje sahibi için)

> **5 Kasım 2026 güncellemesi:** bulguların hepsi düzeltildi ve düzeltmeler bağımsız olarak yeniden denetlendi.
> Puanlar şimdi çekirdek 8/10, savaş 8/10. Ayrıntı ve açık kalan küçük noktalar: Bölüm 7. Aşağıdaki özet raporun
> ilk hâlidir.

- **Temel sağlam, hata yolu zayıf.** Puanlar: çekirdek 5,5/10, savaş 5/10.
  - Kayıt her isteğin sonunda tek seferde yazılıyor, yarım kayıt oluşmuyor.
  - Hata olunca kayıt geri alınıyor.
  - Sunucu yalnızca bu bilgisayardan erişilebilir; dosya yollarından dışarı kaçılamıyor.
  - Savaşın rastgele sayıları istemcininkiyle bit bit aynı; hasar formülü ve düşman yapay zekâsı istemcinin kopyası.
  - Puanı düşüren şey, küçük bir hatanın oyunu kilitlemesi ve sunucunun bazı yerlerde istemciden ayrı hesap yapması.
    İstemci her savaş hamlesini kendi hesabıyla karşılaştırıyor; tutmazsa işlemi kesiyor.
- **Kritik bulgu yok. 6 yüksek önemli bulgu var:**
  1. **CEK-01:** Tek bir hata bütün işlem paketini siliyor ve oyunu kilitliyor. Pek çok başka hatanın oyuncuya yansıma
     biçimi bu; ilk düzeltilecek yer burası.
  2. **CEK-02:** Raffle Center ve üç bina daha yere konunca sunucu çöküyor.
  3. **SAV-01:** Titan savaşlarında sunucu yanlış gücü kullanıyor. Oyuncu Titan'a 8 kat fazla vuruyor, Titan
     Laboratuvarı savaşları istemciyle tutmuyor.
  4. **SAV-02:** Oyuncunun bütün birimleri sersemletilince sunucu çöküyor, savaş donuyor.
  5. **SAV-03:** Yuvarlama farkı yüzünden savaşların yaklaşık %2'sinde düşmanın seçimi istemciden ayrılıyor; istemci
     işlemi kesiyor.
  6. **SAV-04:** Güçle (hava saldırısı vb.) düşman öldürünce ödül verilmiyor; düşmanın gücü oyuncunun birimini
     öldürünce veriliyor.
- **Testler bu hataları göremiyor.** Testler ne kaydın gerçekte saklandığı katmanı (CEK-11) ne de savaşın kendisini
  (SAV-08) çalıştırıyor. Düzeltmeler test-önce yapılmalı.
- **Kararınızı bekleyen 3 konu** var (Bölüm 5.3).

## 1. Kapsam ve yöntem

- **Yalıtım:** her denetçi aynı kodu gördü ama birbirinden ve önceki çalışmalardan habersizdi.
  - Okuma yasağında olanlar: commit mesajları, eski farklar, GitHub PR'ları, `docs/` altındaki öteki raporlar.
  - Denetçilere hiçbir bulgu, hipotez ya da öncelik verilmedi; yalnızca alan ve dosya listesi verildi.
  - Ortak kural metni: [`denetim/BRIEF.md`](denetim/BRIEF.md).
  - Oyuncunun gerçek kurulumuna (`TurkceOyun`) dokunmak ve okumak yasaktı. Denetçiler sunucuyu geçici klasörlerde,
    depodaki örnek kaydın kopyasıyla çalıştırdı.
- **Kanıt şartı:** her bulgu dosya:satır ve alıntıyla ya da çalıştırılan bir betikle kanıtlandı. Her bulgunun güven
  derecesi ayrı yazıldı.
- **Betikler:** `denetim/hesap/cekirdek/` (20 betik) ve `denetim/hesap/savas/` (9 betik). Hepsi yeniden
  çalıştırılabilir ve depoda bir şey değiştirmez.
- **İstemci ölçütü:** istemcinin ne gönderip ne beklediği, oyunun kendi Flash kodundan (`assets/ZGame.109338.swf`,
  `turkce/araclar/abc.py` ile) okundu.

## 2. Bölüm 1 — Sunucu çekirdeği ve kayıt (16 bulgu: Yüksek 2, Orta 9, Düşük 5)

| Kimlik | Önem | Bulgu |
|---|---|---|
| CEK-01 | Yüksek | Bir çağrının hatası bütün paketi düşürüyor; cevap AMF değil, istemci kilitleniyor |
| CEK-02 | Yüksek | Raffle Center (ve 3 öğe) yerleştirilince sunucu çöküyor |
| CEK-03 | Orta | "Nesne yok" koruması günlük satırında çöküyor (list/remove) |
| CEK-04 | Orta | Kilitsiz oku-değiştir-yaz: eş zamanlı istekler ilerlemeyi eziyor |
| CEK-05 | Orta | msgspec'in kodlayamadığı bir değer oturuma girerse kayıt hiç saklanamıyor |
| CEK-06 | Orta | Host denetimi yok; oturum kimlikleri çerezsiz okunabiliyor (DNS rebinding / ağ) |
| CEK-07 | Orta | "Delete save game" tek tıkla kalıcı siliyor; yedek almıyor |
| CEK-08 | Orta | Yerel bir kayıttan ekip (crew) istemek çöküyor |
| CEK-09 | Orta | Ayarları değiştiren bir mod etkinleşince oyun açılmıyor |
| CEK-10 | Orta | Komşu kayıtları pickle ile yazılıyor; ileride okunamayabilir |
| CEK-11 | Orta | Testler kaydın gerçek katmanını hiç çalıştırmıyor |
| CEK-12 | Düşük | Paket başarısız olunca başka kayıtlara ve dosyalara yazılanlar geri alınmıyor |
| CEK-13 | Düşük | Geçersiz kayıtta initUser cevapsız kalıyor |
| CEK-14 | Düşük | Kayıt düzenleyici: yarım yazma, denetimsiz kabul, iki çökme |
| CEK-15 | Düşük | Yedek ve sürüm geçişi ayrıntıları |
| CEK-16 | Düşük | home.html'de dünya adı betiği kırabiliyor |

## 3. Bölüm 2 — Savaş ve PvP (12 bulgu: Yüksek 4, Orta 4, Düşük 4)

| Kimlik | Önem | Bulgu |
|---|---|---|
| SAV-01 | Yüksek | Titan birimlerinde sunucu saldırı gücü yerine dayanıklılığı kullanıyor |
| SAV-02 | Yüksek | Oyuncunun hayatta kalan bütün birimleri sersemlemişken düşman hamlesi sunucuyu çökertiyor |
| SAV-03 | Yüksek | Eşitlik bozmada Python `round()` istemcinin `Math.round`'undan farklı |
| SAV-04 | Yüksek | Güçle öldürmede ödül ve "battleKill" görev ilerlemesi ters tarafa yazılıyor |
| SAV-05 | Orta | Araştırma güç yükseltmesinde sunucu yuvarlamıyor, istemci yuvarlıyor |
| SAV-06 | Orta | Vuruş ödülleri ve ödül zarı istemciden ayrı hesaplanıyor |
| SAV-07 | Orta | "Eski istek" cevabı istemciyi yine hataya düşürüyor |
| SAV-08 | Orta | Savaş testleri savaşın kendisini ölçmüyor |
| SAV-09 | Düşük | Uçaksavar NPC birimleri saldırırsa sunucu çöker |
| SAV-10 | Düşük | Düşmanın ikinci yeteneği ilk adayın oranıyla, ölü birim de sayılarak seçiliyor |
| SAV-11 | Düşük | Bot dengesi belgede biraz iyimser; denge testi tek tohuma bağlı |
| SAV-12 | Düşük | Küçük sağlamlık açıkları (bot durum dosyası, Titan parça açma) |

**Bot dengesi (SAV-11):** denetçi, oyuncunun en kolay ve en zor botlara karşı kazanma oranını yeniden hesapladı.

| | En kolay | | Eşit seviye | | En zor |
|---|---|---|---|---|---|
| Denetçinin ölçümü | %54 | %50 | %45 | %40 | %35 |
| `bot_empires.py`'deki iddia | %58 | %54 | %49 | %39 | %33 |

- Sıralama doğru: kolay botlar daha sık yeniliyor.
- İki kolay basamak, belgede yazandan 4–5 puan zor çıktı. Bu, rastgele seçilen ordulara göre değişiyor.
- "Birebir ayna bot %63 kazanır" iddiası doğrulandı: %62 ölçüldü.

## 4. Bölüm C — Karşıt doğrulama (bulguları raporu yazan taraf yeniden çalıştırdı)

Denetçilerin "kesin" dediği yüksek önemli bulguların hepsini, onların betiklerini çalıştırarak ya da kodu okuyarak
yeniden doğruladım. Hepsi aynen tekrar etti.

| Bulgu | Doğrulama | Sonuç |
|---|---|---|
| CEK-01 | `k01_cokme.py` | Olmayan nesneye list/remove ve olmayan eşya kullanımı: cevap `It went wrong`, AMF değil. Aynı paketteki sağlam `setWorldName` kaydedilmedi. |
| CEK-02 | `k13_tek_define.py`, `k12_odul_alanlari.py` | Raffle Center ve World_Games_Stadium1 yerleştirme çöküyor; 332 durum makineli öğeden 4'ü çözülemiyor. |
| CEK-04 | `k03_kayip_guncelleme.py` | Hiçbir şey değiştirmeyen A isteği, B'nin kaydettiği yeni dünya adını eski ada geri çevirdi. |
| CEK-05 | `k04_kodlanamayan_deger.py` | `undefined` içeren bir çağrı aynı paketteki adı da kaybettirdi. |
| CEK-06 | `k09_ag_guvenligi.py` | Yabancı Host ile çerezsiz `/list_session` kayıt kimliklerini verdi. 6 dosya yolu kaçış denemesinin hepsi 404 (sağlam). |
| CEK-08 | `k16_ekip_istegi.py` | Yerel kayda ekip isteği `KeyError` ile çöktü. |
| CEK-09 | `k15_mod_ayarlar.py` | Mod etkinken gameSettings.xml ve questSettings.xml çöktü. |
| SAV-01 | `titan_hasar.py` | ML11 (seviye 25): oyuncu→Titan hasarı sunucuda 232,7, istemci hesabında 29,1. |
| SAV-02 | `kazalar.py` | `battle_engine.py:1198` `TypeError` ile çöktü. |
| SAV-03 | `yuvarlama_mac.py 1000` | 1000 maçta 21 maçta (%2,1) düşmanın seçimi istemciden ayrıldı. Python `round(0.5)=0`, AS3 `Math.round(0.5)=1`. |
| SAV-04 | `battle_engine.py:1070` okundu, `kazalar.py` | Ödül `if ally:` altında, yani ölen oyuncunun birimi olunca veriliyor. Güçle düşman öldürmek 0, kendi birimini kaybetmek +9 para ve +1 XP verdi. |

Kendim doğrulamadıklarım:
- İstemcinin tepkisine dair iddialar (yeniden deneme, "senkron dışı", hata ile kesme) bytecode okumasına dayanıyor; oyunda denenmedi.
- SAV-05, SAV-06, SAV-07 ve SAV-10'u ve CEK-12 ile CEK-16 arasındaki düşük önemli bulguları yeniden çalıştırmadım.

## 5. Birleşik öncelik sırası

### 5.1 Hemen (her biri ayrı PR, test-önce)

1. **CEK-01 — hata yolu.**
   - Her çağrı ayrı yakalanmalı ve ayrı geri alınmalı; hata veren çağrıya istemcinin anladığı nötr bir AMF cevap
     dönmeli.
   - Bu tek düzeltme CEK-02, CEK-03, CEK-08, SAV-02 ve SAV-09 gibi çökmelerin oyunu kilitlemesini durdurur.
     Çökmelerin kendisi yine ayrıca düzeltilmeli.
2. **SAV-03 — yuvarlama.** `round(x)` yerine istemcinin yaptığı gibi yarımı yukarı yuvarlamak (`floor(x + 0.5)`).
   Küçük bir değişiklik; etkisi ölçülebilir (%2 → %0 hedefi, `yuvarlama_mac.py` ile).
3. **SAV-02 — sersemletme çökmesi** ve **SAV-04 — ödülün tarafı.** İkisi de birkaç satırlık değişiklik.
4. **SAV-01 — Titan saldırı gücü.** Hasar formülünde saldıranın `attackStrength`'i kullanılmalı.
5. **CEK-02 — durum makinesi araması.** Tek `define` sözlüğü ve iki kez tanımlanmış makine güvenle işlenmeli.
6. **CEK-04 — eş zamanlı yazma.** Değişmeyen kayıt geri yazılmamalı ve oyuncu başına kilit kullanılmalı.

### 5.2 Sonra

- **Testler:** CEK-11 (gerçek oturum katmanıyla bir uçtan uca test) ve SAV-08 (savaş turu, yapay zekâ, ödül, tohum
  uyumu testleri). Bu testler 5.1'deki düzeltmelerle birlikte büyür.
- **Diğer düzeltmeler:**
  - CEK-03, CEK-05, CEK-08 (çökme ve kodlama).
  - SAV-05, SAV-06, SAV-07 (istemciyle hesap uyumu).
  - SAV-11: bot belge sayılarını çok tohumla yeniden ölçüp güncellemek.
  - SAV-12 ve CEK-12 ile CEK-16 arasındaki düşük önemli bulgular.
  - CEK-10: pickle yerine msgspec.

### 5.3 Proje sahibinin kararını bekleyenler

1. **Kayıt silme (CEK-07):** silmeden önce otomatik yedek alınsın ve bir onay sorusu gelsin mi? Öneri: evet, ikisi de.
2. **Ağ erişimi (CEK-06):** `/list_session` sayfası yalnız bu bilgisayardan ve doğru adresten (Host denetimi) mi
   açılsın? Öneri: evet. Oyunu başka bir bilgisayardan oynamak (`--host 0.0.0.0`) sizin için gerekli mi? Gerekli
   değilse bu mod belgede uyarıyla kalsın.
3. **Ayar modları (CEK-09):** `mods/` altındaki ayar modları şu an açılınca oyun açılmıyor. Zaten açılmaması gereken
   107829 modu da bunların arasında. Seçenekler: modlar düzeltilsin ya da ayar modları kaldırılsın. Öneri: önce
   düzeltilsin, 107829 modu ise kapalı kalsın.

## 6. Sınırlar ve dürüstlük notu

- İki denetçi ve doğrulayan taraf aynı model ailesinden (Claude), ayrı bağlamlarda çalıştı. Farklı bir ekip ya da
  insan denetçi kadar bağımsız sayılmamalı.
- Gerçek Flash istemcisi çalıştırılmadı. İstemcinin tepkileri bytecode okumasından çıkarıldı. Eş zamanlı yazma (CEK-04)
  istek sırası elle ayarlanarak gösterildi; oyunda ne sıklıkta olduğu ölçülmedi.
- **Kapsam dışı kalan dört bölüm** sonraki turların konusu:
  - Görevler ve etkinlikler.
  - Oyun ayarları ve yamalar.
  - Türkçe çeviri ve araçlar.
  - Kurulum ve belgeler.
- Raporun ilk hâlinde hiçbir bulgu düzeltilmemişti. Düzeltmeler ve onların bağımsız yeniden denetimi Bölüm 7'de.

## 7. Düzeltme durumu — 5 Kasım 2026

Bölüm 5'teki bütün bulgular aynı dalda (`denetim-1`) düzeltildi. Sonra iki yeni bağımsız denetçi düzeltmeleri
inceledi. Onlara da hiçbir sonuç söylenmedi; yalnız eski raporlar ve kod farkı verildi.

- Çekirdek yeniden denetimi: [`denetim/yeniden-cekirdek.md`](denetim/yeniden-cekirdek.md), betikler
  `denetim/hesap/yeniden-cekirdek/` (`y01`…`y07`).
- Savaş yeniden denetimi: [`denetim/yeniden-savas.md`](denetim/yeniden-savas.md), betikler
  `denetim/hesap/yeniden-savas/`.

**Puanlar:** çekirdek 5,5 → **8/10**, savaş 5 → **8/10**. Yeniden denetimin bulduğu 5 yeni sorunun 4'ü de düzeltildi
(aşağıda). Bütün testler geçiyor: `pytest -q` → **193 passed**. Yeni testlerin çoğu gerçek kayıt katmanından ve savaşın
kendisinden geçiyor.

### 7.1 Bulgu bulgu

| Kimlik | Durum | Ne yapıldı |
|---|---|---|
| CEK-01 | Düzeltildi | Her çağrı ayrı korunuyor (`guarded_call`): çağrıdan önce kaydın kopyası alınıyor, hata olursa yalnız o çağrı geri alınıyor ve oyuna `errorType 100` dönüyor. Sağlam çağrılar kaydediliyor. Oyunun kodunda bu cevabın sessizce geçildiği doğrulandı. |
| CEK-02 | Düzeltildi | Tek `define`'lı ve iki kez tanımlı durum makineleri çözülüyor. Raffle Center ve öteki 3 öğe artık yerleşiyor. |
| CEK-03 | Düzeltildi | Günlük satırları boş listede çökmüyor; günlük işlevleri hiçbir zaman çağrıyı düşürmüyor. |
| CEK-04 | Düzeltildi | Aynı kayda gelen istekler kayıt başına bir kilitle sırayla işleniyor. Kilit hata yollarında da bırakılıyor. |
| CEK-05 | Düzeltildi | `undefined` ve ByteArray değerleri kaydedilebiliyor. Kaydedilemeyen bir değer bırakan çağrı ayrıca geri alınıyor (YC-02). |
| CEK-06 | Düzeltildi | Yalnız IP adresi ya da `localhost` adıyla gelen istekler kabul ediliyor (DNS rebinding'e karşı). Socket.IO da bu denetimden geçiyor (YC-01). |
| CEK-07 | Kısmen | Silmeden önce yedek alınıyor ve onay soruluyor. Kalan: yedek yeni oturumdan arayüzle geri getirilemiyor; silme hâlâ bir GET isteği. |
| CEK-08 | Düzeltildi | Yerel kayıttan ekip istemek çökmüyor. |
| CEK-09 | Düzeltildi | Ayar modları açıkken oyun açılıyor. Örnek mod `_with_fixes` dosyasına bağlandı; 107829 modu kapalı kaldı. |
| CEK-10 | Düzeltildi | Komşu kayıtları da msgspec ile yazılıyor; eski pickle kayıtlar sunucu açılırken dönüştürülüyor. Bu sırada bulunan eski bir hata da düzeldi: başka kayda her yazım `.db` adı yüzünden çöküyordu. |
| CEK-11 | Düzeltildi | `test/session_layer_test.py`: gerçek flask-session + SQLAlchemy + msgspec katmanından geçen 22 test. |
| CEK-12 | Kısmen | Başka kayıtlara yazımlar çağrı başarılı olana kadar bekletiliyor. Kalan: `bot_empires.py`, `event_buildings.py` ve `quest_trees.py`'nin dosya yazımları bekletilmiyor. |
| CEK-13 | Kısmen | Geçersiz kayıtta initUser artık cevap alıyor. Kalan: oyunun `TInitUser` işleminde hata karşılığı yok, oyun yine yükleme ekranında kalıyor (bu oyunun tarafı). |
| CEK-14 | Düzeltildi | Kayıt düzenleyici yazmadan önce denetliyor; eksik alan, bozuk JSON ya da sözlük olmayan kayıt 400 dönüyor, kayıt değişmiyor. |
| CEK-15 | Kısmen | Yedek alınamazsa seviye atlama ve sürüm geçişi durmuyor; 0.02a geçişinden önce de yedek alınıyor; 0.08a kayıtların sürümü güncelleniyor. Kalan: geçiş yedeği, kaydın bir kısmı değiştikten sonra alınıyor. |
| CEK-16 | Düzeltildi | Dünya adı ve arkadaş listesi sayfa betiğine güvenli yazılıyor (`script_json`). |
| SAV-01 | Düzeltildi | Titan'lar saldırı gücüyle vuruyor, seviye istemci gibi seçiliyor. 390 vuruşun hepsi istemciyle aynı. |
| SAV-02 | Düzeltildi | Bütün birimler sersemletilmişken sunucu çökmüyor. |
| SAV-03 | Düzeltildi | Bütün yuvarlamalar istemcinin `Math.round`'u gibi (`as3_round`). 400 savaşta, 7334 hamlede tek ayrılık yok. |
| SAV-04 | Düzeltildi | Güçle öldürmenin ödülü ve "battleKill" ilerlemesi doğru tarafa yazılıyor. |
| SAV-05 | Düzeltildi | Araştırma yükseltmesinden sonra güç yuvarlanıyor. |
| SAV-06 | Düzeltildi | Vuruş ödülleri ve ödül zarı oyunun ayarlarından, istemcinin sırasıyla hesaplanıyor. |
| SAV-07 | Düzeltildi | Eski savaş isteğine `data: None` dönüyor; istemci bunu hata saymıyor. |
| SAV-08 | Kısmen | Savaş turu, yapay zekâ, ödül ve güç testleri eklendi (`test/battle_turn_test.py`). Kalan boşluklar yeniden denetim raporunda. |
| SAV-09 | Düzeltildi | Uçaksavar NPC'leri çökertmiyor. |
| SAV-10 | Düzeltildi | Düşmanın ikinci yeteneği istemcinin sırasıyla seçiliyor. |
| SAV-11 | Düzeltildi | Düzeltilmiş motorla yeniden ölçüldü (54 takım, takım ve bot başına 20 savaş, savaşları motorun kendisi oynadı): %54, %50, %45, %40, %35; ayna bot %62. Belgedeki sayılar bunlarla değiştirildi. Denge testi, kendi kopyasının motorla aynı sonucu verdiğini de denetliyor. |
| SAV-12 | Düzeltildi | Bot durum dosyası güvenli yazılıyor; `invasion_complete` eksik alanda çökmüyor; Titan parçası para yetmezse açılmıyor. |

### 7.2 Yeniden denetimin yeni bulguları

| Kimlik | Önem | Durum | Ne yapıldı |
|---|---|---|---|
| YC-01 | Düşük | Düzeltildi | Socket.IO bağlantıları da Host denetiminden geçiyor (`KnownHostsOnly`); yabancı adla 403. |
| YC-02 | Düşük | Büyük ölçüde | Çağrıdan sonra kayıt bir kez deneme olarak kodlanıyor; kodlanamıyorsa yalnız o çağrı geri alınıyor. Kayıt düzenleyici bozuk girişte 400 dönüyor. Not Defteri aynı anda yalnız bir kez açılıyor. Kalan: çağrıların dışındaki seyrek hatalarda (ör. veritabanı yazılamazsa) paket yine düşüyor. |
| YC-03 | Düşük | Açık | Başka bir kayda yazım o kaydın kilidini almıyor. O kayıt aynı anda başka bir tarayıcıda açıksa komşuya yapılan yardım kaybolabilir. İki tarayıcıda iki kayıtla oynamayı gerektiriyor. |
| YS-01 | Orta | Düzeltildi | Güç (hava saldırısı vb.) yalnız birimi öldürünce ödül ve zar alıyor, istemci gibi. Son puanla öldürme de istemci gibi sayılıyor. |
| YS-02 | Düşük | Düzeltildi | Rastgele meydan okuma filoları oyuncunun seviyesiyle gidiyor; Titan iki tarafta aynı seviyede. |

YS-01, asıl denetimdeki SAV-04/06 açıklamasının bir yanlışından çıktı: güç vuruşunun her hasarda ödül verdiği
sanılmıştı, oysa istemci yalnız öldürmede veriyor. Düzeltme oyunun koduna göre yapıldı.

### 7.3 Bedel ve sınırlar

- **Bedel:** her çağrı için kaydın kopyası (~2,6 ms) ve deneme kodlaması (~0,8 ms), 490 KB'lık bir kayıtta. Bir pakette
  birkaç çağrı olduğu için oyuncu fark etmez.
- **Bilerek dokunulmayanlar:** `SESSION_REFRESH_EACH_REQUEST` olduğu gibi kaldı (değiştirmek oturum süresini etkiler).
- **Hâlâ denenmeyenler:** gerçek Flash istemcisi otomatik olarak çalıştırılmadı; istemcinin tepkileri bytecode'dan
  okundu. DNS rebinding tarayıcıda denenmedi. Açık kalan beş nokta (CEK-07, CEK-12, CEK-13, CEK-15, YC-03) düşük ya da
  orta önemde ve oyunu bozmuyor; sonraki bir turda ele alınabilir.
