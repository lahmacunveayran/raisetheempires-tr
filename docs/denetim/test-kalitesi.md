# Test kalitesi: ölçüm, iki denetim ve düzeltmeler (5-6 Kasım 2026)

**Soru (proje sahibi):** "Yapay zekâların yazdığı testler öylesine, geçsin diye mi yazılmış? Doğruysa düzelt, iki kez denetle, ikinci denetim bağımsız olsun."

**Kısa cevap:** Hayır, "öylesine" değillerdi. Ama dar bir alanı kapsıyorlardı ve bazıları kendi kendini doğruluyordu. Bu iki sorun ölçüldü, bağımsız denetlendi ve büyük ölçüde düzeltildi. Testler ilk turdan önce 193 taneydi, bugün 300'ün üzerinde. Bu sırada testler oyunda 5 gerçek hata ortaya çıkardı.

Ham veriler ve betikler: [hesap/test-kalitesi/](hesap/test-kalitesi/). İçindeki yollarda `<S>` geçici çalışma klasörü, `<HOME>` kullanıcı klasörü yerine kullanıldı.

## 1. Yöntem ve kaynaklar

Bir testin iyi olduğunu kapsam oranı göstermez. Gösteren, testin gerçek bir hatayı yakalayıp yakalamadığıdır. Bu yüzden şu ölçüler kullanıldı:

| Ölçü | Ne gösterir | Dayanak |
|---|---|---|
| **Fail-to-pass** | Düzeltme geri alınınca test başarısız olmalı. Olmuyorsa test o hatayı korumuyor demektir. | SWE-bench (Jimenez ve ark., ICLR 2024) değerlendirme ölçütü |
| **Mutasyon testi** | Kod bilerek bozulur (mutant). Testlerin bunun ne kadarını yakaladığı ölçülür. | Just ve ark., *Are mutants a valid substitute for real faults?*, FSE 2014: mutant yakalama, kapsamdan bağımsız olarak gerçek hatalarla ilişkili. Petrović ve ark. (Google), *Practical Mutation Testing at Scale*, ICSE-SEIP 2018 / TSE 2021: yalnızca değişen satırlar mutasyona uğratılır. |
| **Dal kapsamı** | Hangi kodun hiç çalışmadığını gösterir. Yalnız başına kalite ölçüsü değildir. | Inozemtseva ve Holmes, *Coverage is not strongly correlated with test suite effectiveness*, ICSE 2014 |
| **Beklenen değerin kaynağı (oracle)** | Beklenen değer bağımsız bir yerden mi geliyor (istemcinin bayt kodu, oyun XML'i, girdiden elle türetme), yoksa sunucunun kendi çıktısının kopyası mı (anlık görüntü), ya da hiç türetmesi olmayan bir sayı mı? | Yapay zekâ testlerinin bilinen asıl zayıflığı beklenen değer ve "mutlu yol" eğilimidir (bu çalışmada taranan LLM test üretimi literatürü) |
| **Sıra ve kararlılık** | Testler karışık sırayla, ters sırayla ve tekrar tekrar çalıştırıldı. | — |
| **Bağımsız denetim** | Kodu verip sonucu vermeden ayrı bir denetçi çalıştırıldı. | — |

## 2. Birinci tur (5 Kasım): ölçüm ve ilk düzeltmeler

**Elle yapılan bozmalar.** Düzeltilen hatalar koda tek tek geri konuldu: 103 bozma. Testlerin yakaladığı oran **%68'den (70/103) %98'e (101/103)** çıktı.
- Yakalanmayan 2 bozmanın ikisi de eşdeğer: davranışı değiştirmiyorlar (E40: `A != v or p(A)` ile `p(v)`, A == v iken aynı; BE26: ölü hedefin komşuluğu 0, hasarı da 0).
- Kanıt: `hesap/test-kalitesi/tur1/` (`mutations.py`, `final.json`, `final2.jsonl`).

**Bulunan gerçek hata: Titan'lar kara gücünden 2 kat hasar almıyordu.**
- İstemcide (`UnitItem.getModifier`) birimin **bütün** türleri arasında **ilk** eşleşen `<against>` geçerli. Sunucu yalnızca birincil türe ve araziye bakıyordu.
- Düzeltildi ve test edildi (cb00c06).

**Güvenlik açığı: testler bir kez ekranda Not Defteri açtı.** Sebebi, bir test iş parçacığının testten uzun yaşaması ve eski çökme günlüğü kodu. `conftest.py` bunu artık bütün koşu boyunca engelliyor.

**mutmut (araç) ölçümü.**
- Savaş dosyalarında değişen satırlarda 59 mutant sağ kaldı. Bunlar ikinci turda sınıflandırıldı.
- Kayıt dosyalarında ölçüm yarım kaldı: mutmut 2.5.1'in süre sınırı Windows'ta çalışmıyor ve kilidi bozan bir mutant 2 saat kilitlendi. Bu yüzden sonraki ölçümlerde süre sınırlı kendi koşturucumuz kullanıldı.

## 3. Bağımsız denetim (denetim 2): not 6/10

Rapor: `hesap/test-kalitesi/denetim2/rapor.md`. Denetçi önceki raporları ve commit mesajlarını okumadı.

**Hüküm:** testler "sırf geçsin diye" yazılmamış. 227 test fonksiyonunun %67'sinin beklenen değeri bağımsız bir kaynaktan geliyor. Testlerin korumayı iddia ettiği davranışlarda hedefli 25 bozmanın 25'i de yakalandı. **Ama testler dar:**
- **Dal kapsamı:** bütün kodda %47,8, sunucu dosyasında %25,5. Satın alma, pazar, eşya kullanma ve yağma hiç denenmiyordu.
- **Rastgele mutasyon skoru:** %69,7 (370/531). Savaşta %79, kayıtta %71, kayıt göçünde %48.
- **Beklenen değerlerin %25'i türetmesizdi:** 16 anlık görüntü ve 41 açıklamasız sayı. Ayrıca 10 döngüsel (beklenen değeri test edilen koddan alan) ve 9 zayıf test vardı.
- **Sıra bağımlılığı:** testler karışık sırayla çalıştırılınca 27-28'i kurulum hatası veriyordu.

Bulgular B-Y1..3 (yüksek), B-O1..8 (orta) ve B-D1..8 (düşük) diye adlandırıldı.

## 4. İkinci tur (5-6 Kasım): düzeltmeler

İş, birbirinin dosyasına dokunmayan 6 yardımcıya bölündü; ortak kurallar `hesap/test-kalitesi/tur2/ORTAK.md`'de. Her yeni test için fail-to-pass kanıtı istendi: toplam 337 kayıt, `tur2/*/f2p.jsonl`.

| Bulgu | Ne yapıldı | Kanıt | Durum |
|---|---|---|---|
| B-O1 sıra bağımlılığı | Sunucu kurulumu bir kez yapılıyor (`_server_setup`), testler `server` fixture'ını kullanıyor | 4 karışık ve ters koşuda 0 hata (önce 27-28) | birleşti |
| B-O2 kurulum kopyası | `configure_app(app)`: `__main__` ve testler aynı kurulumu kullanıyor; Host kontrolünün takılı olduğu test ediliyor | 5/5 kendi mutantı | birleşti |
| B-O8 hata yolları | Bozuk AMF gövdesi, `transactional_session` ve iki ağ geçidi yolu gerçek istekle test ediliyor | sunucu G listesi 23/24 | birleşti |
| B-D1 depoya yazma | Günlük ve önbellek geçici klasöre gidiyor; koşu sonunda depo değişmişse koşu başarısız | — | birleşti |
| B-D2 zamana dayalı bekleme | Kilit izleniyor (`WatchedLock`); zamana bağlı olumsuz kontrol kaldırıldı | S1b öldü | birleşti |
| B-Y1 sunucu kapsamı | 24 uçtan uca AMF testi: satın alma, genişleme, pazar, eşya, dünya adı, yağma, dünya yükleme, ziyaret | sunucu dal kapsamı **%25,8 → %53,9**; 27/27 f2p | birleşti |
| B-O3 slot makinesi / kasa | Ödüller tek tek sabitleniyor; beklenen değişim XML'den ve istemcinin işleyişinden; ağırlıklar binom sınırıyla (yanlış alarm 1e-6) | 21/21 (eski testler 0/21) | birleşti |
| B-D5 / B-D6 zayıf ve döngüsel testler | Mega seri, mini seri ve bot beklentileri testin kendi XML okuyucusundan | yukarıdaki 21'in içinde | birleşti |
| B-D4, B-Y2, B-D3 savaş | Destek eşyaları, araştırma, DoT, süreler, seviye 10+ yapay zekâ, gemi/uçak birimleri istemci modeline eklendi. Sunucunun savaş motoru da istemciye uyduruldu (aşağıda). | 17 f2p | birleşti, **bağımsız denetlenmedi** |
| B-O5, B-Y3 savaş ödülleri, anlık görüntüler | `battle_reward_test.py`; `init_battle` beklentileri görev XML'inden; şarapnel `ChipDamageManager.getDamage` ile; 8 altın JSON dosyası silindi | mutmut listesinin 18/35'i öldü (kalan 17 sınıflandırılmadı) | birleşti, **bağımsız denetlenmedi** |
| B-O6, B-O7, B-O4, B-D7 kayıt | Bütün site dışı istek önekleri, yedek içeriği, yedekten geri dönüş, yedek sayısı (sabit 20), kayıt göçü adımları, `save.db` taşıma | 152 f2p kaydı | birleşti, **yarım** (son kontroller yapılmadı) |

**Yarım kalanlar** (proje sahibinin isteğiyle durduruldu, bulutta sürecek): bkz. [../DEVIR.md](../DEVIR.md).

## 5. Testlerin bulduğu gerçek oyun hataları

| Hata | Oyuncuya etkisi | Kanıt (istemci) | Durum |
|---|---|---|---|
| Titan'lara `<against>` çarpanı uygulanmıyordu | Kara gücü Titan'a 2 kat hasar vermiyordu | `UnitItem.getModifier` | düzeltildi (cb00c06) |
| Nakitle alınan genişleme anahtarları (xk01) envantere girmiyordu | Para gidiyor, anahtarlar F5'te kayboluyordu | `Player.buyGameItem` → `addToInventory` | düzeltildi (008865b) |
| Enerji eşyası enerji vermiyordu | Eşya siliniyor, enerji gelmiyordu | `UI.tryUsePlayerEnergies` | düzeltildi (008865b) |
| Enerji doldurma bedavaydı | Bedel hep 0 hesaplanıyordu | `EnergyRefillItem.refillAmount` | düzeltildi (008865b) |
| Savaş motorunda istemciden farklar: DoT'ta `<against>` yok, araştırma hasarı yanlış çarpılıyor, kalkanın tamamen emdiği vuruş 0 hasar veriyor (istemcide en az 1), savaş zinciri yalnızca birincil türe bakıyor, iyileştirme hedef seçimi | Savaş sonuçları istemcinin gösterdiğinden farklı | `BattleHost.resolveAttack`, `CombatChain`, `UnitItem.getModifier` | düzeltildi (ebc12cc), **bağımsız denetim bekliyor** |
| Bozuk tek bir kayıt başka oyuncuların çağrılarını düşürüyordu | save.db'de oyuncusu olmayan bir kayıt varsa yağma, ziyaret ve yardım hata veriyordu | sunucunun kendi listeleri bu kayıtları `validate_save` ile zaten atlıyor | düzeltildi (d676b4b) |
| Genişleme satın alınınca bedel alınmıyor | Genişleme parasız açılıyor | `GMExpansion.buyExpansion` → `Player.buyItem`; `ExpansionItem.getAmount` | **açık**: indirim ve çoklu bedel ayrıntısı doğrulanmadı |

## 6. Sınırlar (dürüstlük notu)

- İkinci turun savaş ve kayıt parçaları birleşti ve bütün testleri geçiyor. Ama bağımsız ikinci bir denetimden geçmediler. Bu, bulutta yapılacak ilk iş.
- **Savaş motorundaki değişiklikler oyunun hesabını değiştirir.** Testler istemcinin modeline göre yazıldı. Gerçek oyunda bir kez denenmesi gerekir; oyuncunun kaydı önce yedeklenmeli.
- Mutasyon skorları örneklemdir. Sunucu dosyasında hiç çalışmayan ~25 fonksiyon kaldı (`tur2/isleyici/cov_with_uncovered.txt`).
- CI Linux'ta Python 3.14 kullanıyor, buradaki ölçümler ise Windows'ta Python 3.12 ile yapıldı. İlk push'ta CI sonucuna bakılmalı.
