# Sunucu çekirdeği ve kayıt — Düzeltmelerin bağımsız yeniden denetimi
Denetçi: bağımsız denetçi (çekirdek, yeniden denetim). Taban: 61ac7a8, incelenen: `denetim-1` çalışma ağacı
(`git diff 61ac7a8 -- . ':!docs'`). Tarih: 5 Kasım 2026.

Betikler `docs/denetim/hesap/yeniden-cekirdek/` altında (`y01`…`y07`). Hepsi eski denetimin `ortam.py`'sini kullanıyor:
gerçek oturum katmanı (flask-session + SQLAlchemy + msgspec), geçici klasör, savespack kopyası, crash_log kapalı.
Çalıştırma (betik klasöründen): `PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y0N_....py`.
Eski `k`-betikleri bugünkü kodla yeniden çalıştırıldı. 61ac7a8 ya da daha eski sunucu kodu çalıştırılmadı.
`pytest -q` → **187 passed** (`test/session_layer_test.py` tek başına 18 passed).

## Özet

**Puan: 8 / 10** (eski denetimde 5,5).

Düzeltmeler büyük ölçüde gerçek ve çalışıyor. En önemli iki sorun kapandı:

1. **Tek bir hata artık bütün paketi götürmüyor.** Paketteki bozuk işlem tek başına geri alınıyor, oyuna "bu işlem
   olmadı" deniyor, sağlam işlemler kaydediliyor. Oyunun kodunda bu cevabın sessizce yutulduğu, oyunun kilitlenmediği
   doğrulandı. Not Defteri artık sunucuyu bekletmiyor.
2. **Aynı kayda aynı anda gelen iki istek artık birbirini ezmiyor.** Gerçek iki iş parçacığıyla denendi: kilit varken
   oyunun değişikliği kalıyor, kilit kapatılınca eski kayıp geri geliyor. Hata yollarında kilit hep bırakılıyor,
   kilitlenme bulunmadı.

Raffle Center, mod ayarları, yerel kayıttan ekip isteme, ana sayfa betiği, `undefined` değerler, pickle kayıtlar ve
kötü niyetli alan adları (DNS rebinding) da düzeldi.

Kalan küçük noktalar:
- Socket.IO bağlantısı alan adı denetiminden geçmiyor. Kötü niyetli bir sayfa oyunun canlı günlüğünü okuyabilir.
  Kayıtları değiştiremez.
- Kaydın kodlanamadığı durumlar gibi işlem dışındaki seyrek hatalarda, paket eskisi gibi bütünüyle düşüyor.
- Başka bir kayda (komşuya) yazılan yardım, o kayıt aynı anda başka bir tarayıcıda açıksa eziliyor.
- Silinen kaydın yedeği alınıyor, ama arayüzden geri getirilemiyor.
- Bozuk kayıtla açılışta oyun yine yükleme ekranında kalıyor.

Yeni bulgu: Kritik 0, Yüksek 0, Orta 0, Düşük 3.

## Bulgu bulgu durum

| Bulgu | Karar | Kanıt (kısa) |
|---|---|---|
| CEK-01 paket düşüyor | **Düzeltildi** (çağrı hataları için; kalan uç → YC-02) | `empires-server.py:953-974` `guarded_call` her çağrıdan önce anlık görüntü alıyor. Hata olunca yalnız o çağrıyı geri alıyor ve `{"errorType": 100, "errorData": <fonksiyon>, "data": None}` dönüyor. `k01`: `setWorldName + useItem(olmayan) -> HTTP 200 application/x-amf`, cevaplar `[errorType 0, errorType 100]`, kayıttaki ad `'YeniAd'`. İstemci tarafı (abc.py): `TransactionManager.onAmfBatchComplete` yalnız 28 (RETRY) ve 29 (FORCE_RELOAD) için paketi yeniden dener (`Transaction.<cinit>`: `RETRY_TRANSACTION 28`, `FORCE_RELOAD 29`). Öteki her değer `onSuccess` → `Transaction.onAmfComplete` → `onFault(errorType, errorData)` yolunu izliyor. `Transaction.onFault` boş, alt sınıfların çoğu yalnız `callsuper`; savaş olanlar `clearCombatPopup` / `PRE_BATTLE_CANCEL` yapıyor. Kuyruk ilerliyor, `inSync` bozulmuyor. 500 işleyicisi `editor.edit`'i ayrı iş parçacığında açıyor (`:3175-3179`). |
| CEK-02 Raffle Center | **Düzeltildi** | `game_settings.py:152` `simple_list(custom_values)`, `:165-171` ilk eşleşmeyi alıyor. `k12`: `çözülemeyen alanlar: {}`. `k13`: `place Raffle Center -> HTTP 200 AMF, nesne 658->659, altın 832840->792840`. Stadium da yerleşiyor. |
| CEK-03 boş liste günlükte | **Düzeltildi** | `logger.py:43` boş listeyi ele alıyor, bütün `report_*` işlevleri `@never_fails` (`:14-24`). `k01`: `list/remove yok nesne -> application/x-amf, 1 cevap`. |
| CEK-04 eş zamanlı ezme | **Düzeltildi** (aynı kayıt için; başka kayıt → YC-03) | `:123-131` kayıt başına `threading.Lock`, `:145-149` `teardown_request` bırakıyor. `y01`: `KİLİTLE: A 1.03 sn, B 1.04 sn, ad 'Kilitli ad'` (B bekledi, değişikliği kaldı). `KİLİTSİZ: B 0.32 sn, B'nin adı ezildi mi: True` (karşı kanıt). Eski `k03` artık geçerli değil: aynı iş parçacığında iç içe açılan iki istek aynı `g`'yi paylaşıyor, kilit atlanıyor. Gerçek sunucuda her istek ayrı iş parçacığında çalışıyor ve sunucu kodunda böyle iç içe istek yok. `SESSION_REFRESH_EACH_REQUEST` hâlâ True. |
| CEK-05 kodlanamayan değer | **Düzeltildi** (bilinen türler; kalan → YC-02) | `:893-896` `dense_arrays` Undefined → None. `enc_hook` (`:3191-3194`) Undefined → None, ByteArray → bytes. `k04`: `saveOptions(undefined alanlı) -> application/x-amf`, `kayıttaki ad: Yeni ad`. |
| CEK-06 Host / rebinding | **Düzeltildi** (HTTP; Socket.IO açığı → YC-01) | `:172-183` yalnız IP ya da localhost. `y01`: `Host: kotu.example -> 403`. `k09` artık çöküyor, çünkü `/list_session` yabancı Host'a JSON değil 403 veriyor. SERVERS.md'ye "There is no login…" uyarısı eklendi. LAN kipinde `/list_session` oturum kimliklerini hâlâ veriyor; bu belgelenmiş bir tasarım tercihi. |
| CEK-07 kayıt silme | **Kısmen** | `:283-284` silmeden önce `create_backup` alınıyor, şablonlarda `confirm()` var. `y04`: `silme öncesi yedek backups.db'de: 1`, ama `yeni oturumdan /save-editor'da ... görünüyor mu: False`. Yedek eski oturum kimliğine bağlı, arayüzden geri getirilemiyor. Silme hâlâ GET ile yapılıyor. |
| CEK-08 yerel kayıttan ekip | **Düzeltildi** | `:2847-2848` double → int, `allies.get(..., {"neighbor": True})`. `k16`: `arkadaş 2681928178598866 (yerel kayıt) -> HTTP 200 AMF`. |
| CEK-09 mod ayarları | **Düzeltildi** | `:862-868` `served_text` bytes / str / Response'u ele alıyor. `k15`: `mod etkin -> 200 b'<settings/>'`. `y04`: depodaki gerçek `active-limited-edition` xmldiff'i `_with_fixes` dosyasına uygulanıyor (`HTTP 200 text/xml, farklı mı: True`). `y05`: mod etkinken sunucunun kendi yamaları (event_buildings, quest_trees) da uygulanıyor. README düzeltildi. |
| CEK-10 pickle komşu kayıtları | **Düzeltildi** | `save_engine.py:255-262` `serializer.encode`. `:265-281` açılışta dönüştürme (`empires-server.py:3246-3247`). `k05`: `komşu kaydının ilk baytı: b'\x8e\xaa'` (msgpack). `y07`: `pickle olan: 8 → hâlâ pickle: 0, içerik aynı: 8`. İkinci çalıştırma hiçbir şeyi değiştirmiyor. |
| CEK-11 testler gerçek katmanı çalıştırmıyor | **Düzeltildi** (boşluklar aşağıda) | `test/session_layer_test.py`: gerçek flask-session + SQLAlchemy + msgspec, ağ geçidi üzerinden 18 test. |
| CEK-12 başka kayda yazım geri alınmıyor | **Kısmen** | Başka kayıtlar çağrı başına erteleniyor (`save_engine.py:233-252`). `y03`: help'in kendisi yazdıktan sonra patlayınca `komşudaki yardım kaydı: None`, oyuncunun görevleri geri alındı. Sağlam help `'1009'` yazdı. Dosyalar ise hâlâ hemen yazılıyor: `bot_empires.py:249-254` (`store_save` bot için `_write_state`), `event_buildings.py:148`, `quest_trees.py:333`. Eski `k05`'in "3 kez aynı yardım" çıktısı artık beklenen davranış: help başarılı ve istemci paketi yeniden göndermiyor. |
| CEK-13 initUser cevapsız | **Kısmen** | Cevap sayısı tamam. `k02`: `2 çağrı → cevap sayısı: 2`. `call_response` boş kalınca `guarded_call` `CALL_FAILED` dönüyor. Ama `TInitUser`'ın `onFault`'u yok (abc.py `classes ^TInitUser$`: yalnız `onComplete`), yani oyun yine yükleme ekranında kalıyor. Fark, kuyruğun kilitlenmemesi. Oyuncu açısından sonuç aynı. |
| CEK-14 kayıt düzenleyici | **Düzeltildi** (küçük kalan → YC-02) | `:552-554` yazmadan önce doğruluyor. `k07`: `eksik 'quests' -> HTTP 400, kayıttaki ad: Rising Empire`. `k06` / `k08`: yeni oturumda ve `saved_on`'suz yedekte `/save-editor -> 200`. Kalan: dict olmayan ya da bozuk JSON → `200 b'It went wrong'` (`y04`). |
| CEK-15 yedek / sürüm | **Kısmen** | Düzelenler: `state_machine.py:222-225` yedek hatası seviyeyi geri almıyor, `save_migration.py:10` 0.02a yedeği, `:70-72` 0.08a kayıtları `save_version`'ı güncelliyor, `empires-server.py:1818` kaydın sürümüyle çağırıyor. `k00`: `save_version: 0.08a.2026_08_13`. `y04`: `'0.07a.2024_11_09' -> '0.08a.2026_08_13'`. Kalanlar: göç yedekleri hâlâ `user_response` kaydı değiştirdikten sonra alınıyor (`:1739` `fleets = {}` … `:1820 migrate`). `migrate` içindeki `create_backup` korumasız; backups.db yazılamazsa initUser `CALL_FAILED` olur ve oyun yüklemede kalır. |
| CEK-16 home.html betik kaçışı | **Düzeltildi** | `:238-240` `script_json` `<`'yi `<` yapıyor, üç şablon da bunu kullanıyor. `save-editor.html` `{{ savegame }}`'i `safe` olmadan basıyor. `k17`: `kaçışsız '</script>…' var mı: False`. |

## Yeni bulgular

### YC-01 — Socket.IO istekleri Host denetiminden geçmiyor; rebinding ile canlı oyun günlüğü okunabilir
- **Önem:** Düşük. **Güven:** el sıkışmanın kabul edildiği kesin (çalıştırıldı). Tarayıcıda rebinding ile sömürülmesi
  olası.
- **Yer:** `empires-server.py:172-183` `reject_unknown_hosts` yalnız Flask isteklerinde çalışıyor. `/socket.io/`
  istekleri engineio ara katmanında Flask'tan önce karşılanıyor. `logger.py:38-50` `socketio.emit` herkese yayıyor.
- **Kanıt:** `y02_socketio.py`:
  ```
  socket.io el sıkışma Host=kotu.example:5005  -> HTTP 200 b'0{"sid":"4SQHth2Ka2BIfzqAAAAB","upgrades'
  karşılaştırma: /home.html Host=kotu.example       -> HTTP 403
  ```
  engineio'nun aynı köken denetimi rebinding'de geçiyor, çünkü Origin ile Host aynı yabancı ad.
- **Oyuncuya etkisi:** Sunucu açıkken ziyaret edilen kötü niyetli bir sayfa, `world_log` / `other_log` olaylarını
  dinleyerek oyunun bütün istek ve cevaplarını görebilir (initUser cevabında kaydın tamamı var). Kayıt değiştiremez,
  oturum kimliği almaz.
- **Önerilen düzeltme:** `SocketIO(cors_allowed_origins=...)` ile yalnız `http://127.0.0.1:<port>` /
  `http://localhost:<port>` kabul edilsin. Ya da engineio `connect` olayında `environ['HTTP_HOST']`'u aynı kurala göre
  reddet. Bunun için bir test ekle.

### YC-02 — Çağrı dışındaki hatalar hâlâ bütün paketi düşürüyor ve AMF olmayan cevap dönüyor; her yeniden denemede yeni bir Not Defteri açılıyor
- **Önem:** Düşük. **Güven:** mekanizma kesin. Oyunda tetiklenmesi olası; bilinen pyamf türleri artık kodlanıyor.
- **Yer:** `empires-server.py:3175-3179` (500 işleyicisi hâlâ `'It went wrong'` dönüyor, HTTP 200 text/html), kaydın
  yazıldığı `save_session` (`guarded_call`'un dışında).
- **Kanıt:** `y01_kilit.py`, bir çağrı oturuma kodlanamayan bir değer koyduğunda:
  ```
  save_session hatası (object() oturumda) -> HTTP 200 text/html; charset=utf-8 | AMF DEĞİL: b'It went wrong'
     kayıttaki ad (sağlam setWorldName kaldı mı?): 'Kilitli ad'   <- aynı paketteki sağlam çağrı da kayboldu
  ```
  `pyamf.flex.ObjectProxy` ve XML (`ElementTree.Element`) msgspec'te hâlâ kodlanamıyor; `enc_hook` yalnız Undefined
  ile ByteArray'i çeviriyor. Bunun dışında: düzenleyiciye dict olmayan ya da bozuk JSON gönderilirse yine
  `200 b'It went wrong'` (`y04`). crash_log açıkken her 500 yeni bir `editor.edit` iş parçacığı başlatıyor.
  İstemci paketi `m_amfMaxRetries` kez yeniden gönderdiği için her denemede ayrı bir Not Defteri penceresi açılır.
- **Oyuncuya etkisi:** Seyrek, ama olduğunda eski CEK-01 gibi: paket her denemede düşer, oyun senkron dışı kalır,
  ekrana birkaç Not Defteri penceresi açılır.
- **Önerilen düzeltme:** `guarded_call`'da çağrıdan sonra `serializer.encode(dict(session))` ile bir deneme kodlaması
  yap. Başarısız olursa o çağrıyı geri al ve `CALL_FAILED` dön (çağrı başına ~2 ms anlık görüntüyle aynı düzeyde).
  Ağ geçidi yolunda 500 işleyicisi AMF hata zarfı dönsün. `save_savegame`'de `isinstance(save_game, dict)` ve
  `json.loads` hatasını 400'e çevir. Not Defteri'ni yalnız bir kez aç (ör. açık bir pencere varken yenisini açma).

### YC-03 — Başka bir kayda yazım o kaydın kilidini almıyor; o kayıt açıksa yazılan eziliyor
- **Önem:** Düşük. **Güven:** mekanizma kesin (çalıştırıldı). Oyunda sıklığı olası: iki tarayıcıda iki ayrı kayıtla
  oynayan ya da bir kaydın sayfasını açık tutan oyuncu gerekir.
- **Yer:** `save_engine.py:255-262` `write_session` komşunun kaydını kilit almadan yazıyor. Kilit yalnız çerezdeki
  kayıt için var (`empires-server.py:126-131`). `SESSION_REFRESH_EACH_REQUEST` True kaldığı için hiçbir şey
  değiştirmeyen istekler bile kaydı geri yazıyor.
- **Kanıt:** `y06_baska_kayit_kilidi.py` (B komşunun kaydıyla `/home.html` açmış, A o sırada komşuya help yapıyor):
  ```
  help cevabı: [0] | Y'de yardım, help'ten hemen sonra: '1005' | Y'nin açık isteği bitince: None
  ```
- **Oyuncuya etkisi:** Komşuya yapılan yardım ya da püskürtme/işgal izi komşunun kaydından sessizce kaybolur, oysa
  yardım eden oyuncunun kaydında görev ilerlemesi kalır.
- **Önerilen düzeltme:** `write_session`, hedef kaydın kilidini de alsın (`session_interface.locks[sid]`). Kilitler
  hep aynı sırayla alınmalı ya da `acquire(timeout=...)` kullanılmalı ki iki kayıt birbirine yazarken kilitlenme
  olmasın. Ayrıca `SESSION_REFRESH_EACH_REQUEST = False` yapılsın; değişmeyen oturum geri yazılmaz, pencere büyük
  ölçüde kapanır.

### Sağlam bulunanlar (yeni kod)
- **İstemci cevap biçimi:** `CALL_FAILED = 100` istemcinin hiçbir özel koduyla çakışmıyor (0, 1, 10, 26-29). Paketin
  üst `errorType`'ı 0 ve cevap sayısı korunuyor. `no_data_response` (`data: None`) `onAmfComplete`'te `onComplete`'i
  çağırmıyor, `TResolveBattle` için doğru.
- **Kilit hata yollarında bırakılıyor** (`y01`, her biri ardından aynı kayıtla bir isteği 5 sn içinde bitirdi): Host
  403, 404, görünüm hatası (500), iç `open_session` hatası, `save_session` hatası. Socket.IO olayları da
  (`_handle_event` → `app.request_context`) kilidi alıp bırakıyor. Paket sürerken gelen olay bekliyor, sonra
  bitiyor (`y02`). Kilitlenme yok. İstek içinde ikinci bir Flask isteği açan kod yok (sunucu kodunda `test_client` /
  `test_request_context` / iç içe `app_context` aranıp bulunmadı).
- **Ertelenen yazım** çağrı başına çalışıyor. Aynı paketteki sonraki çağrı öncekinin yazdığını görüyor (`y03`).
- **Maliyet:** seviye 85 kayıtta anlık görüntü 1,8 ms. 1 / 10 / 30 çağrılık paket ort. 34 / 52 / 132 ms (`y03`).
  Kilit, kayıt kullanan istekleri sıraya koyuyor. Varlık yolları kilit almıyor.
- **Host denetimi:** `[::1]:5005`, `localhost`, LAN IP'si geçiyor. `127.0.0.1.evil.example` reddediliyor (test ve
  kod okuma).

## Testlerin değeri

`test/session_layer_test.py` gerçek katmanı kullanıyor ve düzeltmelerin çoğunu bozulunca yakalayacak biçimde ölçüyor:
- `test_a_failing_call_is_undone_and_the_other_calls_are_kept`: cevap biçimini, sağlam çağrıların kalmasını, yarım
  değişikliğin (`half_done`) geri alınmasını ve başka kayda ertelenmiş yazımı birlikte denetliyor. Anlık görüntü ya da
  erteleme bozulursa düşer.
- `test_overlapping_requests_of_one_save_wait_for_each_other`: gerçek iş parçacıklarıyla çalışıyor. Kilit kaldırılırsa
  `assert not fast_done.wait(0.5)` düşer (`y01`'deki kilitsiz deneme bunu doğruluyor).
- Kayıt düzenleyici, pickle dönüşümü, msgpack yazımı, durum makinesi taraması ve mod (bytes / str) testleri anlamlı.

Bozuk düzeltmeyle de geçecek ya da eksik kalanlar:
- `test_migration_remembers_the_version_of_0_08a_saves` yalnız `migrate()`'i çağırıyor. `user_response`'taki
  `is_0_08a_preview(session.get('save_version'))` düzeltmesi (`:1818`) geri alınsa da geçer.
- `test_world_names_cannot_end_the_home_page_script` yalnız `script_json`'u deniyor. Şablonlar yeniden `json.dumps`
  kullansa da geçer (`k17` bunu yakalıyor).
- `test_an_invalid_save_still_answers_every_call` cevap sayısını ölçüyor. İstemcinin yine yüklemede kalmasını
  (CEK-13) ölçmüyor.
- `test_values_the_client_left_undefined_can_be_saved` ağ geçidinden geçmiyor, iç içe nesnede `undefined` denemiyor
  (`k04` geçiyor).
- `test_list_of_a_missing_object_can_be_logged` `__wrapped__` ile `never_fails`'i atlıyor; ağ geçidi yolu `k01`'de.
- Test yok: Socket.IO Host denetimi (YC-01), kilidin hata yollarında bırakılması, 500 işleyicisinin beklememesi,
  `convert_pickled_saves`'in açılışta çağrılması, seviye atlama yedeğinin `try/except`'i, silme onayı.
- Fikstür global `app`'i değiştiriyor (`_got_first_request = False`, yeni veritabanı adresi) ve yalnız
  `session_interface`'i geri koyuyor. Bugün tüm takım geçiyor, ama test sırasına bağımlılık riski var.

## Bakılamayanlar

- Gerçek Flash istemcisi çalıştırılmadı. `CALL_FAILED`'e tepki `TransactionManager.onAmfBatchComplete`,
  `Transaction.onAmfComplete` / `onFault` ve 40 kadar `onFault` alt sınıfı bytecode'dan okundu.
- Eş zamanlılık Flask test istemcisiyle iki gerçek iş parçacığında denendi, werkzeug sunucusu ve tarayıcıyla değil.
  DNS rebinding tarayıcıda denenmedi.
- İstemcinin `ObjectProxy` ya da XML gönderip göndermediği (YC-02 tetikleyicisi) doğrulanmadı.
- Savaş dosyaları yalnız `store_session` çağıranları açısından okundu (`battle_engine.py:303`, `bot_empires.py:249`).
- `.github/workflows` değişikliği çekirdek dışı olduğu için değerlendirilmedi.
