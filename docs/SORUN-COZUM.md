# Sorunlar ve çözümler (bilgi birikimi)

Bu proje üzerinde çalışırken bulunan, ilk bakışta belli olmayan hatalar ve tuzaklar burada toplanıyor. Her madde bir kez yaşanmış bir sorundan çıktı. Yeni bir hata bulunca buraya ekleyin.

## Kayıt (save)

- **Kayıtların biçimi:** `mygames/save.db`'deki `sessions` tablosunun satırları **msgspec msgpack** biçiminde, pickle değil. `pickle.loads` "truncated" hatası verir, ama bu bozulma değildir. Okumak için `msgspec.msgpack.decode(data)` kullanılır. Etkin kayıt, `user_object`'i olan ve `saved_on`'u en yeni olan satırdır.
- **Kaydı elle düzeltme sırası:**
  1. Oyunu kapat.
  2. empires-server'ı çalıştıran python'u durdur.
  3. `yedekle.py` ile yedek al.
  4. Satırı çöz ve `encode(decode(x)) == x` olduğunu doğrula.
  5. Düzelt, yeniden kodla, satırı güncelle.
  6. Sunucuyu yeniden başlat.

  Sunucu çalışırken düzenleme yapılmaz; sunucu kaydı üzerine yazar.
- **Yedekler** `backups.db`'de tutulur, en fazla 20 tane. Eskiden kaydın içinde iç içe bir zincir olarak saklanıyorlardı; `save_engine` bunları taşır.
- **Başarısız istek:** bir istek başarısız olursa kayıttaki değişiklikleri geri alınır (`transactional_session`). Aynı kaydı açan iki istek birbirini bekler (kayıt kilidi).

## İstemci ve sunucu tuzakları

- **İstemci önce davranır, sunucu sonra kaydeder.** İstemci çoğu işi kendisi uygular ve kendine güvenir; sunucu yalnızca aynısını kaydeder. Yanlış kaydeden bir işleyici oyunda o an doğru görünür, sayfa yenilenince (F5) bozulur. Bu yüzden testten sonra oyunu yeniden yükleyip kontrol etmek gerekir.
- **gameSettings.xml ve questSettings.xml giriş yapılmadan, oturum çerezi olmadan istenir.** Oyuncuya özel veri bunlarda olacaksa bir dosyadan gelmeli (`mygames/quest_tree_spots.json`, `event_buildings.json`). Bu veriye bağlı şeyler bir sonraki sayfa yüklemesinde başlar.
- **Toplu satın alma:** `buy_item` miktar yerine +1 ekliyordu; toplu "hepsini al"da parçalar kayboluyor, para yine de düşüyordu (3e9473c). Başka işleyicilerde de miktar verilen yerde `+ 1` var mı, bakın.
- **`performAction` dönüşü:** yeni bir `performAction` adım işleyicisi `data`'yı `{"id": object_id}` gibi `"id"` içeren bir sözlük olarak döndürmeli, `[]` değil. `logger.report_world_log` `[]` görünce çöker, istek geri alınır ve oyun "net status failure" gösterir (df68d74).
- **Seviyeye bağlı görevler** yalnızca seviye atlanınca başlar. Yüksek seviyeli bir oyuncu eski bir özelliğin görevini hiç almaz (kasa görevi Q140J, seviye 26). Çözüm: girişte bir kez `new_quest` + `do_quest_rewards` ile eklemek. `new_quest_with_sequels` kullanılmaz, çünkü başlamamış bütün seviye görevlerini de başlatır (8a3792f).
- **Çoklu eşyalı `inventoryCount`:** `item="A,B,C"` olan görevler hiç ilerlemiyordu. Artık `quest_engine.inventory_total` kullanılıyor.
- **Bir alanı yazmadan önce istemcinin onu nerede okuduğuna bakın.**
  - Örnek: `PVPManager.init(userData)` `globalPVPOptIn`'i `pvp`'nin içinde değil, `user_object`'in en üstünde okuyor. Yanlış yere yazınca katılma penceresi çıkmıyor ve ekran gri kalıyor.
  - Mod numaraları özellikten özelliğe değişir: slot makinesinde BUY=1 / KEYS=2, kasada 0/1. Değerler `<cinit>` sabitlerinden kontrol edilir.
- **İstemcide tarihler:** `new Date("MM/DD/YYYY")` yerel saatle gece yarısıdır.
  - `requiredDate overrideKey` ZRTManager'a soruyor; çevrimdışı null döner, bu yüzden silinir.
  - `*_with_fixes.xml` etkinlik bitişlerini 2032'ye itiyor; bu da gün sayaçlarını bozuyor.
- **500 sayfası durum kodu:** sunucunun 500 sayfası `It went wrong` metnini **HTTP 200** durumuyla döndürür (Flask, hata işleyicisinin döndürdüğü metne durum koymaz). Bu yüzden testte yalnızca durum koduna bakmak yetmez, gövdeye de bakılır.

## Asset'ler (SWF ve resimler)

- **Eksik dosyalar:** yeni SWF'lerin ve sembollerin çoğu eksik; yereldeki `sol_assets_octdict` SWF'leri eski sürümler. Bir dosyanın varlığı `quest_trees._asset_exists(url)` ile kontrol edilir; bu fonksiyon SWF'in içindeki sembole de bakar.
- **Gri, boş ekran:** SWF'i eksik bir pencere demektir. `sunucu.log`'da `GET /nullassets/...` 404'üne bakın.
  - Çözüm: `empires-server.py`'deki `ASSET_STAND_INS`, eksik yolu aynı taban sınıflı başka bir pencerenin SWF'ine yönlendirir. Örnek: `MechLabName.swf` → `PU_NameNation.swf` (d1233a8).
  - Benzer pencereyi bulmak için `refs:<swf adı>` ile sınıfı, onun üst sınıfını, sonra kardeş sınıfların `assetURL`'ini bulun.
- **Savaş sonu donması:** savaş sonunda ekran karanlıkta donarsa sonuç penceresinin SWF'i eksiktir. `PU_Pvp_Defeat.swf`, `turkce/araclar/pvp_yenilgi.py` ile üretildi.
- **Birim animasyon adları:** `Units_*.swf` içindeki SymbolClass adları `.png` ile biter (`Unit_..._Anim.png`). Kontrol ederken bu ek atılır.
- **Gerçek kanıt istemcidir.** Statik alan adı kontrolü yetmez: kodun okumaz göründüğü alanları yeniden adlandırmak PvP yenilgi penceresini bozdu.

## İstemciyi okumak: abc.py

- **Kullanım:** `python turkce/araclar/abc.py assets/ZGame.109338.swf <komut>`.
  - `strings <regex>`: regex zorunlu.
  - `classes <regex>`: sınıfları arar.
  - `method <Sınıf> <ad>`: metodu söker. `"<cinit>"` statik sabitleri verir.
  - `refs <regex>`: bir adı kimin kullandığını gösterir.
- **İşlemler:** `T*` sınıfları `signedWorldAction('<adım>')` çağırır; bu, sunucudaki `performAction` adımıdır. `onComplete(result)` istemcinin yanıttan hangi alanları okuduğunu gösterir.
- **Savaş kuralları:** `BattleAI.GetAttackingDamage`, `Battle.resolveAttack`, `getDiceRoll`, `CombatChain.getHitValue`, `UnitItem.getModifier` (`<against>`), `ZGameRandom` (iki MWC üreteci, 3 basamakta kesme).
- **Git Bash'te `/tmp` yolu:** Python için Windows yolu değildir. `$(cygpath -w /tmp)` kullanın.

## Savaş

- **Hasar formülü:** `25 · Dmax · (3·Amax + Dcur) / (3·Dcur + Amax) / 100`.
  - Sıyırma vuruşu ×0,10, kritik vuruş ×1,5.
  - Vuruş türü `combatChain`'den gelir.
  - Ardından 3 basamakta kesilir ve yukarı yuvarlanır (ceil).
- **Birlik türleri sonucu belirler.** Hasar savunanın kendi en yüksek gücüyle ölçeklenir; güç yalnızca oranlar üzerinden etki eder. Asıl belirleyici birlik türlerinin eşleşmesidir.
- **Consumable `<against>` kuralı:** istemcide birimin **bütün** türleri arasında **ilk** eşleşen `<against>` geçerlidir (`UnitItem.getModifier`). Sunucu eskiden yalnızca birincil türe ve araziye bakıyordu, o yüzden Titan'lar kara gücünden 2 kat hasar almıyordu. Düzeltildi.
- **Oyuncunun vuruşu:** düşmanı 1 güçte bırakacaksa +1 eklenir ve birim ölür.

## Testler: yöntem ve tuzaklar

- **İyi testin ölçüsü kapsam değildir; testin hata yakalayıp yakalamadığıdır.**
  - Kod bilerek bozulur (mutant) ve testin başarısız olduğu görülür (fail-to-pass).
  - Beklenen değer bağımsız bir kaynaktan gelmeli: istemcinin bayt kodu, oyun XML'i ya da girdiden elle türetme.
  - Sunucunun kendi çıktısının dökümü (anlık görüntü / snapshot) doğruluğu değil, yalnızca değişmezliği ölçer.
  - Ayrıntı: `docs/denetim/test-kalitesi.md`.
- **Tek-örnek kilidi:** `tendo.singleton.SingleInstance()` kilidin adını `sys.argv[0]`'dan alır. Windows'ta iki `python -m pytest` aynı anda çalışırsa ikincisi PermissionError verir. Aynı anda koşmak için her biri farklı yoldaki bir başlatıcı betikle çalıştırılmalı; örneği `docs/denetim/hesap/test-kalitesi/run_pytest.py`.
- **PYTHONPATH:** depo kökünü göstermeli. Göstermezse `ModuleNotFoundError: init_settings` çıkar.
- **mutmut 2.5.1:**
  - Windows'ta süre aşımı çalışmıyor. Kilidi bozan bir mutant testi sonsuza kadar kilitledi ve iş 2 saat takıldı. Bu yüzden süre sınırlı kendi koşturucumuz kullanılır.
  - Kodu yerinde değiştirir; yalnızca bir kopya üzerinde (worktree) çalıştırılmalı.
  - `--use-patch-file` için `whatthepatch` paketi ve `git diff --no-prefix` gerekir; yoksa sessizce 0 mutant üretir.
  - Windows'ta `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` gerekir.
  - mutmut 3 Windows'ta çalışmaz.
- **Testler ekranda Not Defteri açabilir.**
  - Sebebi: eski kodda (61ac7a8 ve öncesi) 500 işleyicisi çökme günlüğünü metin editöründe açıyordu. Bir test isteği iş parçacığı (thread), testin monkeypatch'i geri alındıktan sonra çökünce editör açılıyordu.
  - Şimdi `conftest.py` bunu bütün koşu için kapatıyor, eşzamanlılık testi de iş parçacıklarını `finally` içinde bekliyor.
  - Eski koda karşı test çalıştırmayın.
- **Satır sonları:** bu bilgisayarda `core.autocrlf=true`, yani çoğu dosya depoda LF, çalışma kopyasında CRLF. Depoda gerçekten CRLF olan kod dosyaları yalnızca `empires-server.py` ve `battle_engine.py` (kontrol: `git ls-files --eol | grep i/crlf`). `sed -i` kullanılmaz; düzenleyici dosyanın kendi satır sonunu korumalı. Normal `git commit` yeterli; commit'ten önce `git diff --stat` ile dosyanın baştan sona değişmediğine bakın.
- **Testler save.db'yi paylaşır:** `server` fixture'ı her testten sonra save.db'yi boşaltır. Bir test başka oyuncu gerekiyorsa onu kendisi oluşturmalı; önceki testlerin kayıtlarına güvenmemeli. Sunucunun bütün kayıtları dolaşan kodu (`get_saves`) bozuk kayıtları `validate_save` ile atlar.
- **Yapay zekâ ajanlarının çalışma kopyaları** (`.claude/worktrees/…`) bazen eski bir commit'ten (a499313) açılıyor. İşe başlamadan önce doğru dala sıfırlayın.

## Oyunu bilgisayarda sürmek (gerçek istemciyle test)

- **Tarayıcıyı başlatma:** paketteki Chromium (`TurkceOyun/chromium/chrome.exe`) `--remote-debugging-port=9333` ile başlatılır ve CDP üzerinden sürülür.
- **Koordinatlar:** CSS koordinatı = ekran görüntüsü pikseli / 1,25.
- **Sayfa yüklendikten sonra:** `#loading_game` gizlenir ve `scrollTo(0,276)` yapılır.
- **Oturum:** test için ayrı bir oturum çerezi kullanılır; bitince kullanıcının çerezi geri konur.
- **Oyunda hata ayıklama:** `mygames/sunucu.log`'da modül çıktılarına bakılır ("Event ", "Quest complete", fonksiyon adları, Traceback). Günlük her isteğin parametrelerini gösterir.
