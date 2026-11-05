# Sunucu çekirdeği ve kayıt — Bağımsız denetim raporu
Denetçi: bağımsız denetçi (sunucu çekirdeği ve kayıt). Kaynak: denetim-1 @ a4de86e. Tarih: 31 Ekim 2026.

## Özet

**Puan: 5,5 / 10.**

Kaydın temel taşıyıcısı sağlam: kayıt her isteğin sonunda tek bir SQLite yazımıyla saklanıyor (yarım yazılmış kayıt
oluşmuyor), paketteki bir çağrı hata verince oyuncunun kaydı isteğin öncesine geri alınıyor, yedekler kaydın dışına
taşınmış ve sayısı sınırlı, sunucu varsayılan olarak yalnız bu bilgisayardan erişilebilir, dosya yollarından dışarı
kaçmak mümkün değil. Puanı düşüren şey **hata yolu**: sunucudaki herhangi bir küçük hata oyunu kilitliyor ve o paketteki
bütün işlemleri siliyor; ayrıca testler kaydın gerçekte saklandığı katmanı hiç çalıştırmıyor, bu yüzden aşağıdaki
hataların çoğunu testler yakalayamıyor.

Yazılımcı olmayan biri için en önemli noktalar:

1. **Tek bir hata bütün paketi götürüyor ve oyunu kilitliyor (CEK-01).** Oyun işlemleri sunucuya paket hâlinde
   gider. Paketteki tek bir işlem hata verirse sunucu oyuna anlayamayacağı bir cevap ("It went wrong") yollar, paketteki
   sağlam işlemler de silinir. Oyun aynı paketi tekrar dener, yine aynı hatayı alır ve sonunda "senkron dışı" kalır;
   oyuncu sayfayı yenilemek zorunda kalır, o arada yaptıkları kaydedilmemiş olur. Bilgisayarda her hatada Not Defteri
   açılır ve kapatılana kadar sunucu o isteği bekletir.
2. **Raffle Center yerleştirilemiyor (CEK-02).** 40.000 altına satılan Raffle Center (ve üç bina daha) yere konduğu
   anda sunucu hata veriyor; madde 1'deki kilitlenme yaşanıyor.
3. **Aynı anda iki istek gelirse ilerleme ezilebilir (CEK-04).** Sunucu her istekte (bir sayfa açmak bile) kaydın
   tamamını geri yazıyor ve kilit kullanmıyor. Oyun bir işlem kaydederken sayfa yenilenir ya da ikinci sekmede bir sayfa
   açılırsa, eski kayıt yenisinin üstüne yazılabiliyor.
4. **Kayıt silme tek tık ve geri dönüşsüz (CEK-07).** "Delete save game" kaydı save.db'den hemen siliyor; öncesinde yedek
   almıyor ve eski yedekler yeni oturumdan görülemiyor.
5. **Ağ güvenliği (CEK-06).** `/list_session` sayfası, çerez istemeden bütün kayıtların oturum kimliklerini (kayıtların
   anahtarı) veriyor ve sunucu gelen isteğin hangi adrese yapıldığını denetlemiyor. Kötü niyetli bir sitenin "DNS
   rebinding" ile ya da sunucu SERVERS.md'deki gibi `--host 0.0.0.0` ile açıldığında ağdaki herhangi birinin kayıtları
   okuması, değiştirmesi, silmesi mümkün.

Bulgu sayısı: Kritik 0, Yüksek 2, Orta 9, Düşük 5 (toplam 16).

Tüm betikler `docs/denetim/hesap/cekirdek/` altında. Her biri sunucuyu **gerçek oturum katmanıyla** (flask-session +
SQLAlchemy + msgspec, yani oyundaki gibi) geçici bir klasörde kurar (`ortam.py`); save.db olarak depodaki
`savespack/save.db`'nin bir kopyasını kullanır. Depoya ve oyuncunun kurulumuna yazmaz. Çalıştırma (betik klasöründen):
`PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe kNN_....py`

## Bulgular

### CEK-01 — Bir çağrının hatası bütün paketi düşürüyor; cevap AMF değil, istemci kilitleniyor
- **Önem:** Yüksek. **Güven:** kesin (sunucu tarafı, çalıştırıldı); istemcinin tepkisi yüksek (bytecode okundu).
- **Yer:** `empires-server.py:823-842` (`transactional_session`), `:860-1307` (`post_gateway` döngüsü, çağrı başına
  koruma yok), `:3078-3082` (500 işleyicisi).
- **Kanıt:**
  ```python
  @app.errorhandler(500)
  def server_error_page(error):
      if settings.crash_log:
          text = editor.edit(filename=os.path.join(log_path(), "log.txt"))   # Not Defteri kapanana kadar bekler
      return 'It went wrong'                                                # HTTP 200, text/html
  ```
  `k01_cokme.py` çıktısı (seviye 75 kayıt):
  ```
  setWorldName + useItem(olmayan) -> HTTP 200 text/html; charset=utf-8 | AMF DEĞİL (DecodeError): b'It went wrong'
  kayıttaki dünya adı: 'Titan_alpha-test' (önce: 'Titan_alpha-test')
    log.txt: KeyError: 'OLMAYAN_ESYA'  <- empires-server.py", line 2623, in use_item_response
  ```
  Sağlam `setWorldName` da geri alındı (geri alma doğru çalışıyor, ama paketin tamamı için). İstemcide
  `TransactionManager.onAmfBatchFault` aynı paketi `m_amfMaxRetries` kez yeniden gönderir (sunucu her seferinde aynı
  hatayı verir), sonra çağrıları `onFailure` ile düşürür ve `inSync = false` yapar; bundan sonra `batchCall` yalnızca
  "Unable to batch call because client is out-of-sync!" yazar, hiçbir işlem sunucuya gitmez.
- **Oyuncuya etkisi:** Oyuncu birkaç bina toplar, bir eşya kullanır; eşya sunucunun kaydında yoksa (istemci ile sunucu
  hafifçe ayrışmışsa) paket düşer, toplamalar da kaybolur, oyun donar ya da senkron dışı uyarısı verir. crash_log
  açıkken (varsayılan) her denemede bir Not Defteri penceresi açılır ve cevap o kapatılana kadar gelmez.
- **Önerilen düzeltme:** Döngüde her çağrıyı ayrı `try/except` ile sar: çağrı öncesi anlık görüntü al, hata olursa
  yalnız o çağrının değişikliklerini geri al, günlüğe yaz ve o çağrı için nötr bir cevap ekle (cevap sayısı korunur).
  Ağ geçidi için 500 işleyicisi AMF hata zarfı dönsün; `editor.edit` istek iş parçacığında çağrılmasın (ayrı iş
  parçacığında ya da yalnız süreç çökerken).

### CEK-02 — Raffle Center (ve 3 öğe) yerleştirilince sunucu çöküyor
- **Önem:** Yüksek. **Güven:** kesin (sunucu tarafı); istemcinin bu binayı mağazada gösterdiği olası (ayarlarda
  `buyable="true" placeable="true"`, maliyet 40.000 altın).
- **Yer:** `state_machine.py:23-25, 63-66` → `game_settings.py:152` ve `:166` (çağıran çekirdek, hata
  game_settings'te).
- **Kanıt:** `define` tek öğe olduğunda JSON'da liste değil sözlük oluyor; `{e['-name']: ... for e in custom_values}`
  sözlüğün anahtarlarını (dizgi) dolaşıyor. `WorldGamesStadiumStateMachine` ayarlarda iki kez tanımlı;
  `[state_machine] = [...]` iki sonuçla patlıyor. `k12_odul_alanlari.py` (332 durum makineli öğenin hepsini dener):
  ```
  ('World_Games_Stadium1', ..., 'ValueError', 'too many values to unpack (expected 1)'),
  ('Raffle Center', 'RaffleStateMachine', 'TypeError', "string indices must be integers, not 'str'"),
  ('Energiser Transmitter', ..., 'TypeError', ...), ('CommandoAnimation', ..., 'TypeError', ...)
  ```
  `k13_tek_define.py`: `place Raffle Center -> HTTP 200 b'It went wrong' | nesne sayısı 658->658, altın 832840->832840`.
- **Oyuncuya etkisi:** Raffle Center'ı satın alıp yere koyan oyuncu CEK-01'deki kilitlenmeyi yaşar; bina hiçbir zaman
  kaydedilmez.
- **Önerilen düzeltme:** `lookup_state_machine`'de `custom_values`'a da `simple_list` uygula; çift tanımlı makinede
  ilkini al (ya da veri dosyasını düzelt). `k12_odul_alanlari.py` gibi bir taramayı teste dönüştür.

### CEK-03 — "Nesne yok" koruması günlük satırında çöküyor (list/remove)
- **Önem:** Orta. **Güven:** kesin.
- **Yer:** `empires-server.py:1988-1994` (koruma `data=[]` döndürür), `:898-900` → `logger.py:27`.
- **Kanıt:** `res = response[0] if isinstance(response, list) else response` boş listede IndexError. `k01_cokme.py`:
  ```
  performAction list   yok nesne -> HTTP 200 text/html | AMF DEĞİL ... b'It went wrong'
  performAction remove yok nesne -> HTTP 200 text/html | AMF DEĞİL ... b'It went wrong'
  performAction move   yok nesne -> HTTP 200 application/x-amf | AMF, 1 cevap
    log.txt: IndexError: list index out of range  <- logger.py", line 27, in report_world_log
  ```
  `test/empires_test.py:468` bu korumayı yalnızca `perform_world_response`'u doğrudan çağırarak test ediyor; ağ
  geçidinden geçmediği için hatayı görmüyor.
- **Oyuncuya etkisi:** Pazar binası (Market) üzerinde, sunucuda artık olmayan bir nesneye "listele/kaldır" gelirse oyun
  CEK-01 gibi kilitlenir; korumanın amacı tam da bunu önlemekti.
- **Önerilen düzeltme:** `report_world_log`'da boş liste ve dizgi durumunu ele al; bütün `report_*` çağrılarını
  `try/except` ile sar (günlük yazmak oyunu asla düşürmemeli). Testi `post_gateway` üzerinden yaz.

### CEK-04 — Kilitsiz "oku-değiştir-yaz": eş zamanlı istekler ilerlemeyi eziyor
- **Önem:** Orta. **Güven:** mekanizma kesin (çalıştırıldı); oyunda sıklığı olası.
- **Yer:** `empires-server.py:105-124` (yalnız varlık yolları atlanıyor), `:3149` (`socketio.run` → threaded=True);
  flask-session 0.8 `save_session` (her istekte `_upsert_session`).
- **Kanıt:** `k03_kayip_guncelleme.py` (A: tanınmayan bir yol açılır, B: oyun dünya adını değiştirir, A biter):
  ```
  SESSION_REFRESH_EACH_REQUEST = True | oturum kalıcı mı (SESSION_PERMANENT): True
  is_asset('/home.html') = False ; is_asset('/files/.../109338/olmayan.swf') = False ; is_asset('/save-editor') = False
  A açıldı, A'nın gördüğü dünya adı: Rising Empire
  B (setWorldName) -> 200 | kayıttaki ad: Oyuncunun yeni adi
  A bitti (hiçbir şey değiştirmedi) -> kayıttaki ad: Rising Empire
  flask_socketio.run threaded=True: True | async_mode: threading
  ```
  İstemci kendi paketlerini sıraya koyuyor (`onAmfBatchSend` yalnız `m_batchedAmfCalls.length == 0` iken gönderir),
  yani iki oyun paketi çakışmaz; çakışan, oyun dışı isteklerdir.
- **Oyuncuya etkisi:** Oyuncu bir şey yapar ve hemen sayfayı yeniler (oyun takıldığında sık yapılır) ya da ikinci
  sekmede ana sayfayı veya kayıt düzenleyiciyi açar: yeni sayfa isteği eski kaydı okur, oyun paketi kaydeder, sayfa
  isteği eski kaydı geri yazar; son işlemler kaybolur. `home.html` bütün kayıtları çözdüğü için pencere geniş.
- **Önerilen düzeltme:** `SESSION_REFRESH_EACH_REQUEST = False` (yalnız değişen oturum yazılsın) ve kayıt üzerinde
  süreç içi bir kilit (ör. oturum kimliği başına `threading.Lock`, kayıt değiştiren yollar için). İstenirse kayda bir
  sürüm sayacı koyup eskisiyle yazmayı reddetmek.

### CEK-05 — msgspec'in kodlayamadığı bir değer oturuma girerse kayıt hiç saklanamıyor
- **Önem:** Orta. **Güven:** mekanizma kesin; istemcinin `undefined` göndermesi olası.
- **Yer:** `empires-server.py:3085-3094` (`enc_hook` bilinmeyeni `TypeError` ile reddeder), istemci verisini olduğu gibi
  kayda koyan işleyiciler (ör. `:2444` saveOptions, `:2421` updateRoads, `:2508` loadWorld `pvpMode`, `:1963`
  referenceItem, `:2565` addFleet).
- **Kanıt:** `pyamf.Undefined` ve `amf3.ByteArray` msgspec'te kodlanamıyor (`k18_msgspec_turleri.py`); `k04_kodlanamayan_deger.py`:
  ```
  setWorldName + saveOptions(undefined alanlı) -> HTTP 200 text/html | AMF DEĞİL ... b'It went wrong'
  kayıttaki ad: Rising Empire
    log.txt: raise TypeError  <- empires-server.py", line 3094, in enc_hook
  aynı ad tek başına -> HTTP 200 | kayıttaki ad: Yeni ad
  ```
  Hata `save_session` içinde, `transactional_session`'ın dışında oluşuyor; flask-session yazmayı 3 kez (0,3 + 0,6 sn
  bekleyerek) deniyor.
- **Oyuncuya etkisi:** İstemci bir alanı `undefined` gönderirse o paket her denemede kaydedilemez, oyun CEK-01'deki
  gibi kilitlenir.
- **Önerilen düzeltme:** `dense_arrays` gelen veride `pyamf.Undefined`'ı `None`'a çevirsin; `enc_hook` bilinen pyamf
  türlerini (Undefined → None, ByteArray → bytes) dönüştürsün.

### CEK-06 — Host denetimi yok; oturum kimlikleri çerezsiz okunabiliyor (DNS rebinding / LAN)
- **Önem:** Orta. **Güven:** kesin (sunucu tarafı); tarayıcının rebinding'e izin vermesi olası.
- **Yer:** `empires-server.py:152-158` (Origin/Referer yalnız `request.host` ile karşılaştırılıyor), `:261-282`
  (`/list_session` ve `get_sessions_dropdown_info` `session_id` döndürür), `SERVERS.md:7-25` (`--host 0.0.0.0`).
- **Kanıt:** `k09_ag_guvenligi.py`:
  ```
  Çerezsiz GET /list_session (Host: kotu-site.example:5005) -> 200, 2 kayıt; ilk kimlik: session:c519d7e7-...
  Aynı kimlikle 'kendi' sitesinden GET /gazillionaire -> 302 /home.html | reject_cross_site_save_changes engellemedi
  ```
  Oturum kimliği kaydın tek anahtarıdır (imza yok, `SESSION_USE_SIGNER=False`).
- **Oyuncuya etkisi:** Sunucu açıkken ziyaret edilen kötü niyetli bir sayfa, alan adını 127.0.0.1'e çevirerek bütün
  kayıtların kimliklerini okuyup kayıtları değiştirebilir/silebilir (`/patch`, `/save-editor`, `/wipe_session`).
  SERVERS.md'deki sunucu kipinde (`--host 0.0.0.0`) ağdaki herkes bunu doğrudan yapabilir; hiçbir kimlik doğrulama yok.
- **Önerilen düzeltme:** `before_request`'te `Host` başlığını `127.0.0.1:<port>` / `localhost:<port>` ile sınırla (ayar
  ile genişletilebilir); `/list_session` ve sayfalardaki açılır listede oturum kimliği yerine kısa ömürlü bir anahtar
  kullan; SERVERS.md'ye "kimlik doğrulama yoktur, yalnız güvenilir ağda" uyarısı ekle.

### CEK-07 — "Delete save game" tek tıkla kalıcı siliyor; yedek almıyor, yedekler sahipsiz kalıyor
- **Önem:** Orta. **Güven:** kesin.
- **Yer:** `empires-server.py:245-250`; `templates/save-editor.html:181` (onaysız bağlantı); `save_engine.py:72-75`
  (yedekler oturum kimliğine bağlı).
- **Kanıt:** `k06_kayit_silme.py`:
  ```
  silmeden önce: save.db'de kayıt var mı: True | backups.db'de bu kaydın yedeği: 1
  GET /wipe_session -> 302 /login.html
  sonra: save.db'de kayıt var mı: False
  backups.db'de hâlâ duran yedek: 1
  ```
  `session.clear()` flask-session'da kaydı veritabanından siler (`_delete_session`); yeni oturumun kimliği farklı
  olduğu için `list_backups` eski yedekleri göstermez.
- **Oyuncuya etkisi:** Kayıt düzenleyicide yanlışlıkla "Delete save game"e basan oyuncunun aylarca süren kaydı gider;
  yedeği diskte durduğu hâlde arayüzden geri getirilemez.
- **Önerilen düzeltme:** Silmeden önce `create_backup("Silmeden önce")`; GET yerine POST + onay; silinen kayıtların
  yedeklerini listeleyip geri yükleyebilen bir sayfa (backups.db'de `save_id` zaten var).

### CEK-08 — Yerel bir kayıttan ekip (crew) istemek çöküyor
- **Önem:** Orta. **Güven:** kesin.
- **Yer:** `empires-server.py:2758`.
- **Kanıt:** `auto_accept_friends = [f for f in friends if allies[str(f)]["neighbor"]]` yalnız `allies/` klasöründeki
  hazır komşuları biliyor; arkadaş listesi ise öteki yerel kayıtları da içeriyor (`get_allies_friend` →
  `get_sessions_friends`). `k16_ekip_istegi.py`:
  ```
  crewRequest arkadaş 111 (allies/ komşusu) -> HTTP 200 AMF
  crewRequest arkadaş 2681928178598866 (yerel kayıt) -> HTTP 200 b'It went wrong'
    log.txt: KeyError: '2681928178598866.0'  <- empires-server.py", line 2758, in crew_request_response
  ```
- **Oyuncuya etkisi:** Birden çok kaydı olan (çok oyunculuğu yerel kayıtlarla taklit eden) oyuncu, Parlamento için
  kendi öteki kaydından ekip isteyince oyun kilitlenir.
- **Önerilen düzeltme:** `allies.get(str(f), {}).get("neighbor")` ile yerel kayıtları da kabul et (ya da sessizce
  atla). Not: büyük uid'ler AMF3'te double olarak gelip `str()` ile `"...0"` oluyor (yukarıdaki anahtar); uid
  karşılaştırmalarında `int(float(x))` kullan.

### CEK-09 — Ayarları değiştiren bir mod etkinleşince oyun açılmıyor
- **Önem:** Orta. **Güven:** kesin.
- **Yer:** `empires-server.py:566-567` ve `:582-583` (`send_from_directory_mod` mod varsa `bytes` döndürür, kod
  `.direct_passthrough` atar; `:549` flashFile bunu doğru ele alıyor).
- **Kanıt:** `k15_mod_ayarlar.py`:
  ```
  /gameSettings.xml            modsuz -> 200 | mod etkin -> 200 b'It went wrong'
  /127.0.0.1questSettings.xml  modsuz -> 200 | mod etkin -> 200 b'It went wrong'
    log.txt: AttributeError: 'bytes' object has no attribute 'direct_passthrough'
  ```
  Depodaki `gameRevision_107829_settings` ve `gameRevision_57372` modları tam bu dosyaları değiştiriyor. Ayrıca
  `mods/README.md`'nin örnek modu `active-limited-edition` yalnız `gameSettings.xml`'i değiştiriyor; sunucu ise
  `gameSettings_with_fixes.xml` sunduğu için bu mod istemciye hiç ulaşmıyor (belge-kod uyumsuzluğu).
- **Oyuncuya etkisi:** README'deki tarife uyup `mods.conf`'ta bu modlardan birini `true` yapan oyuncunun oyunu
  yüklenmez.
- **Önerilen düzeltme:** flashFile'daki `isinstance(response, Response)` kalıbını bu iki yola da uygula; örnek modu
  `_with_fixes` dosyasına taşı ya da README'yi düzelt.

### CEK-10 — Komşu kayıtları pickle ile yazılıyor; flask-session'ın kaldıracağı geri dönüşe bağımlı
- **Önem:** Orta (bakım riski). **Güven:** kesin.
- **Yer:** `save_engine.py:233-240` (`record.data = pickle.dumps(dict(save))`), `bot_empires.py:246-253`; flask-session
  `base.py` `MsgSpecSerializer.decode`: `# TODO: Remove the pickle fallback in 1.0.0`.
- **Kanıt:** `k05_baska_kayit_geri_alinmaz.py` son satırı: `komşu kaydının ilk baytı: b'\x80\x04' (0x80 = pickle)`.
  savespack'teki 8 kaydın hepsi de pickle (`k19_savespack_bicim.py`). Sunucunun kendi yazdığı kayıtlar msgpack.
- **Oyuncuya etkisi:** Bugün sorun yok (0.8.0 sabitlenmiş). flask-session 1.0'a yükseltilirse, bir kez komşu
  ziyareti/işgali almış ya da eski sürümden gelen her kayıt açılamaz (`UnpicklingError`) ve listeden "kaybolur".
- **Önerilen düzeltme:** `store_session` `sess_int.serializer.encode(...)` kullansın; açılışta pickle kayıtları bir
  kez msgpack'e çeviren bir dönüşüm ekle.

### CEK-11 — Testler kaydın gerçek katmanını hiç çalıştırmıyor
- **Önem:** Orta. **Güven:** kesin.
- **Yer:** `test/empires_test.py:12-13`, `test/save_actions_test.py:9-10`, `test/state_machine_test.py:6-7` (hepsi
  `Flask(__name__)` + çerez oturumu); `test/conftest.py` yalnız backups.db'yi yönlendiriyor.
- **Kanıt:** Hiçbir test `sess.init_app`/`db.init_app` çağırmıyor; msgspec kodlama/çözme (`enc_hook`,
  `decode_objects`), `AssetSkippingSessionInterface`'in gerçek iç katmanla davranışı, hata sonrası cevap biçimi,
  `save_migration.py` (hiç testi yok), kayıt düzenleyici POST'u ve `/wipe_session` test edilmiyor. CEK-01, 03, 04, 05,
  07, 09 ve 13 bugünkü 147 geçen testin hiçbirinde görünmüyor. `test_post_gateway` yalnız tek bir başarılı çağrıyı
  deniyor.
- **Önerilen düzeltme:** `docs/denetim/hesap/cekirdek/ortam.py`'deki kurulum gibi gerçek oturum katmanlı bir pytest
  fikstürü; ağ geçidi üzerinden "bir çağrı patlarsa cevap sayısı ve biçimi" testi.

### CEK-12 — Paket başarısız olunca başka kayıtlara ve dosyalara yazılanlar geri alınmıyor
- **Önem:** Düşük. **Güven:** kesin.
- **Yer:** `empires-server.py:2517-2534` (`store_session` paket ortasında komşuya yazar), `:823-842` yalnız oturumu
  geri alır (bot_empires.json, event_buildings.json, quest_tree_spots.json da kapsam dışı).
- **Kanıt:** `k05_baska_kayit_geri_alinmaz.py` (help + hatalı çağrı, istemcinin yeniden denemesi gibi 3 kez):
  ```
  deneme 1 -> HTTP 200 b'It went wrong' | komşudaki visitorHelpRequests[...] = '1005'
  deneme 2 -> ... = '1005,1005'
  deneme 3 -> ... = '1005,1005,1005'
  ```
- **Oyuncuya etkisi:** Komşu kaydı açıldığında aynı yardım üç kez oynatılır (`accept_tend_ally_response` her öğe için
  `click_next_state`), fazladan ödül; oyuncunun kendi kaydında ise yardımın hiç izi yoktur.
- **Önerilen düzeltme:** Başka kayıtlara/dosyalara yazmayı paket başarıyla bitene kadar ertele (bir "yapılacak yazımlar"
  listesi, `after_request`'te uygula).

### CEK-13 — Geçersiz kayıtta initUser cevapsız kalıyor; istemci yüklemede donuyor
- **Önem:** Düşük. **Güven:** kesin (sunucu); istemci tepkisi yüksek.
- **Yer:** `empires-server.py:876-881`.
- **Kanıt:** `except InvalidSaveException` hiçbir cevap eklemiyor. `k02_gecersiz_kayit.py`:
  `2 çağrı gönderildi -> HTTP 200 application/x-amf | cevap sayısı: 1`. İstemci `onAmfBatchComplete`
  `data.length == m_batchedAmfCalls.length` değilse yalnız "ERROR - batch results is not an array of length" yazar,
  çağrıların `onSuccess`'i çalışmaz, kuyruk boşalmaz; yeni paket gönderilmez.
- **Oyuncuya etkisi:** Sayfa yüklendikten sonra kayıt bozulursa (ör. başka sekmede düzenleyiciyle) oyun yükleme
  ekranında kalır. Sayfalar açılışta `validate_save` ile düzenleyiciye yönlendirdiği için seyrek.
- **Önerilen düzeltme:** Bu durumda da bir cevap ekle (`errorType` sıfırdan farklı) ya da paketin tamamına AMF hata
  zarfı dön.

### CEK-14 — Kayıt düzenleyici: yarım yazma, denetimsiz kabul ve iki çökme
- **Önem:** Düşük. **Güven:** kesin.
- **Yer:** `empires-server.py:495-529` (`save_savegame` `transactional_session` ile sarılı değil, `validate_save`
  yok), `:472` (yeni oturumda `session['quests']` KeyError), `:533-537` (`datetime.fromtimestamp(None)`).
- **Kanıt:** `k07_duzenleyici_yarim_yazma.py`:
  ```
  eksik 'quests' -> HTTP 200 b'It went wrong' | kayıttaki ad: YARIM | quests hâlâ eski mi: True
  geçersiz user_object -> HTTP 302 /home.html | validate_save: False
  ```
  `k06`: yeni oturumla `/save-editor -> 200 b'It went wrong'`. `k08_yedek_listesi.py`: `saved_on`'u olmayan bir kayıttan
  alınan yedek eklenince `/save-editor -> 200 b'It went wrong'` (`format_backup_message({'saved_on': None}) ->
  TypeError`). savespack kayıtlarında `saved_on` var; bu ancak çok eski kayıtlarda görülür.
- **Oyuncuya etkisi:** Elle düzenlemede bir anahtar eksik kalırsa kayıt yarı yeni yarı eski olur; yedekten geri
  yükleme ekranı bazı eski kayıtlarda hiç açılmaz.
- **Önerilen düzeltme:** Önce bütün anahtarları ve `validate_save`'i denetle, sonra yaz; `format_backup_message`'da
  `backup.get('saved_on') or 0`; `/save-editor` GET'te `session.get('quests', [])`.

### CEK-15 — Yedek ve sürüm geçişi ayrıntıları
- **Önem:** Düşük. **Güven:** kesin (kod okuması).
- **Yer ve kanıt:**
  - `state_machine.py:222`: seviye atlamada `create_backup` oyun paketinin içinde ve korumasız; backups.db
    yazılamazsa (kilit, disk dolu) seviye atlayan her paket CEK-01 gibi düşer. Yedek, paketin ortasındaki durumu
    saklar.
  - `save_migration.py:9-26`: 0.02a dalı görevleri ve genişlemeleri sıfırlıyor ama öncesinde yedek almıyor (öteki
    dallar alıyor). `:28`, `:52` yedekleri `user_response` kaydı zaten değiştirdikten sonra (`:1648-1729`) alınıyor.
  - `save_migration.py:50-69` ve `empires-server.py:1730`: "0.08a" sürümlü (önizleme olmayan) kayıtlar için hiçbir dal
    çalışmıyor, `save_version` hiç güncellenmiyor (savespack c519d7e7: initUser sonrası hâlâ `0.08a`, `k00_duman.py`);
    `is_0_08a_preview(version)` kaydın değil sunucunun sürümüyle çağrılıyor, hep False.
- **Oyuncuya etkisi:** Bugün küçük; ileride sürüm dizgisine dayanan bir göç eklendiğinde 0.08a kayıtları yanlış dala
  düşebilir.
- **Önerilen düzeltme:** `create_backup`'ı `try/except` ile "en iyi çaba" yap; 0.02a dalına yedek ekle; göç sonunda
  `session['save_version'] = target_version`; `is_0_08a_preview(session.get('save_version'))`.

### CEK-16 — home.html'de dünya adı betiği kırabiliyor
- **Önem:** Düşük. **Güven:** kesin.
- **Yer:** `templates/home.html:39` (`return {{ allies | safe | default([]) }};`), `empires-server.py:179-180`
  (`json.dumps`, `</` kaçırılmıyor).
- **Kanıt:** `k17_ana_sayfa_kacis.py`: bir kaydın adı `</script><b id=enjekte>x</b><script>` yapılınca öteki kaydın
  ana sayfasında `kaçışsız '</script><b id=enjekte>' var mı: True`.
- **Oyuncuya etkisi:** Adında `</script>` geçen bir kayıt, öteki kayıtların ana sayfasında oyunu başlatan betiği
  bozar; oturum çerezi `HttpOnly=False` olduğu için kendi kendine XSS de mümkün.
- **Önerilen düzeltme:** `{{ allies_list | tojson }}` (Jinja `tojson` `<`'yi kaçırır) ya da `json.dumps(...)
  .replace("</", "<\\/")`.

## Sağlam bulunanlar

- **Varsayılan dinleme adresi yerel:** `init_settings.py:6` `host = '127.0.0.1'`; `--host` verilmedikçe ağdan
  erişilemez.
- **Dosya yolu kaçışı yok:** `send_from_directory_mod` werkzeug `safe_join` + `send_from_directory` kullanıyor; mod
  araması yalnız sözlük anahtarıyla. `k09`: `/assets/../../RaiseTheEmpires.ini`, `..%2f`, `..%5c`, `C:/Windows/win.ini`,
  `%2e%2e` denemelerinin hepsi 404. `ASSET_STAND_INS` doğru çalışıyor
  (`/nullassets/displays/dialogs/MechLabName.swf -> 200 application/x-shockwave-flash`).
- **Siteler arası istek:** Çerez `SameSite=Strict` (`:140`) olduğu için başka siteden gelen istek oyuncunun kaydını
  taşımaz; kayıt değiştiren GET yolları da Origin/Referer denetiminden geçiyor (`:152-158`, testli). JS'in
  `login()`/`changeSession()` ile koyduğu SameSite'sız çerez, bir sonraki sunucu cevabında yeniden Strict olarak
  yazılıyor. (Host denetimi eksikliği ayrı: CEK-06.)
- **Paket geri alma çalışıyor:** Gerçek oturum katmanında `transactional_session` hata olunca oturumu geri yüklüyor ve
  Flask hata yolunda bu geri yüklenmiş hâli kaydediyor (`k01`: dünya adı değişmedi). Kayıt yalnız istek sonunda tek
  bir SQLite işlemiyle yazıldığı için istek ortasında süreç ölürse bir önceki kayıt sağlam kalır.
- **İstemci paketleri sıralı:** `TransactionManager.onAmfBatchSend` yeni paketi yalnız bekleyen paket yokken
  gönderiyor; tek istemciden iki ağ geçidi isteği çakışmaz.
- **Varlık istekleri oturumu atlıyor:** `AssetSkippingSessionInterface` (`:105-124`) resim/swf/ayar isteklerinde kaydı
  okumuyor/yazmıyor; Ruffle'ın `/127.0.0.1flashservices/gateway.php` yolu doğru biçimde hariç (testli). Socket.IO
  istekleri engineio ara katmanında karşılandığı için kaydı geri yazmıyor.
- **Yedekler:** Kayıt içindeki yedek zinciri `backups.db`'ye taşınıyor, kayıt başına en çok 20 yedek, sıra korunuyor
  (testli). Maliyet makul: seviye 85 kayıtta `create_backup` ortalama 34 ms (`k14`).
- **Performans:** Seviye 85 / 1288 nesneli kayıtta (316 KB msgpack) basit bir paket ortalama 36 ms, en çok 103 ms;
  `get_saves()` 21 ms; istemci swf yaması 0,37 sn (`k14`, ayrı ölçüm). Kayıt düzenleyici formu (`k19`): en büyük örnek kayıt
  URL-kodlanmış 1,03 MB, `MAX_FORM_MEMORY_SIZE` 5 MB; geniş pay var.
- **Durum makinesi verisi:** `parse_duration` oyun verisindeki 98 farklı sürenin hepsini çözüyor (`k11`); ödül/maliyet
  alanları 328 öğede `int()` ile okunabiliyor (`k12`, kalan 4 öğe CEK-02). `autoNext` zincirlerinde 0 süreli döngü
  yalnız `VisitorAvatarStateMachine`'de var (1→2→1; `k10`); bu öğe dünyadaki nesneler arasında değil, sunucu ona
  tıklamayı "nesne yok" diye atlıyor.
- **BattleContext kodlaması:** `msgspec.Struct(tag=True)` olduğu için `{"type": "BattleContext", ...}` olarak
  yazılıyor ve `decode_objects` bunu geri çeviriyor (denendi). `enc_hook`'taki `__type__` dalı hiç çalışmayan ölü kod.
- **Güvenilmeyen veri çözme:** `pickle.loads` yalnız yerel dosyalar (backups.db, sunucunun kendi anlık görüntüsü,
  save.db) için; ağdan gelen veri yalnız pyamf ile çözülüyor.
- Testler: `../venv312/Scripts/python.exe -m pytest -q` → 147 passed.

## Bakılamayanlar ve sınırlar

- Gerçek Flash istemcisi çalıştırılmadı; istemcinin tepkileri (yeniden deneme, senkron dışı, cevap sayısı denetimi)
  `abc.py` ile `TransactionManager` bytecode'u okunarak çıkarıldı. "It went wrong" gövdesine Flash'ın tam olarak hangi
  NetConnection olayıyla tepki verdiği denenmedi.
- İstemcinin hangi alanları `undefined` gönderdiği (CEK-05) ve uid'leri Number mı String mi gönderdiği (CEK-08 notu)
  doğrulanmadı.
- Eş zamanlılık (CEK-04) gerçek iki iş parçacığıyla değil, istek sırası elle kurularak gösterildi; oyunda ne sıklıkla
  çakıştığı ölçülmedi. DNS rebinding'in oyunla gelen Chromium'da işe yaradığı denenmedi.
- İşleyicilerin oyun kuralı doğruluğu (ödül miktarları, savaş, görevler, ekonomi) bu alanın dışında bırakıldı; yalnız
  kaydı bozan ya da paketi düşüren yollar incelendi. Socket.IO günlüğüne JSON'a çevrilemeyen bir cevap gönderilirse
  (debug sayfası açıkken) ne olacağı denenmedi.
- Betikler `%TEMP%` altında geçici klasörler ve tendo kilit dosyaları bırakır; depoda yalnız bu rapor ve
  `docs/denetim/hesap/cekirdek/` yazıldı.
