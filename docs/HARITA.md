# Proje haritası: Raise the Empires Türkçe

Bu sayfa projedeki her parçanın ne işe yaradığını ve nerede durduğunu anlatır. İlk kez bakan biri (insan ya da yapay zekâ) buradan başlamalı. Sorunlar ve çözümleri için bkz. [SORUN-COZUM.md](SORUN-COZUM.md), son durum ve sıradaki işler için bkz. [DEVIR.md](DEVIR.md).

## Oyunun yapısı

- **İstemci:** 2013'te kapanan Zynga oyununun Flash istemcisi, `assets/ZGame.109338.swf`. Kodu değiştirilmez; gerekirse küçük bayt yamaları yapılır (`client_patches.py`). Oyunun kuralları bu dosyada yazılıdır. Sunucu bir şeyi hesaplarken doğru cevap istemcinin kodudur.
- **Sunucu:** Python 3.12 ve Flask. Zynga'nın sunucusunun yerini tutar. İstemci AMF biçiminde istek gönderir (`/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php`, Ruffle için `/127.0.0.1flashservices/gateway.php`). Sunucu oyuncunun kaydını `save.db`'de tutar.
- **İstemcinin çoğu işi kendisi yapar.** Sunucu çoğunlukla aynısını kayda yazar. Sunucu yanlış kaydederse oyun o an doğru görünür, sayfa yenilenince (F5) bozulur.

## Kök klasördeki Python dosyaları

| Dosya | Ne yapar |
|---|---|
| `empires-server.py` | Ana sunucu (~3300 satır). Flask rotaları, AMF ağ geçidi, `performAction` adımları, satın alma, pazar, kayıt düzenleyici (`/save-editor`), site dışı istek koruması, 500 sayfası. `configure_app(app)` sunucunun kurulumudur; testler de onu kullanır. |
| `save_engine.py` | Kaydın yüklenmesi ve yazılması, kayıt kilidi, yedekler (`backups.db`, en fazla 20), kayıt doğrulama, eski pickle kayıtların çevrilmesi, çökme günlüğü. |
| `save_migration.py` | Eski sürüm kayıtlarını yeni sürüme taşır (0.02a → … → 0.08a). |
| `battle_engine.py` | Savaş hesabı: zar, hasar, kritik ve sıyırma vuruşları, destek eşyaları (consumable), yapay zekânın hamlesi, ödüller. İstemcinin `BattleAI`, `Battle`, `CombatChain`, `UnitItem` kodlarını izler. |
| `state_machine.py` | Binaların ve nesnelerin durum makineleri (inşaat, üretim, tıklama). |
| `quest_engine.py`, `quest_settings.py` | Görevler: açılma, ilerleme, ödüller; `gated_quests` ve `reward_overrides` kancaları. |
| `game_settings.py`, `init_settings.py`, `language_settings.py`, `mod_engine.py` | Oyun ayarlarının (XML) okunması, sunucu ayarları (`RaiseTheEmpires.ini`), dil ve mod sistemi (`mods/`). |
| `logger.py` | Dünya günlüğü. |
| `quest_trees.py` | Mini seriler (QT…), istemci yamasıyla birlikte. |
| `megaseries.py` | Mega seriler (MS02–MS04). |
| `event_buildings.py` | Parça etkinlikleri: yanardağ, göktaşı, derin deniz sondajı, kasırga, nükleer. |
| `titan_lab.py` | Titan laboratuvarı (TL01): parça kilidi, etkinleştirme, ödül savaşı. |
| `treasure_vault.py` | Hazine kasası (TV01). Asıl ödül tabloları kayıp, tablolar bizim. |
| `slot_machine.py` | Küresel PvP'nin slot makinesi. |
| `bounty_center.py` | Ödül avcısı merkezi (BCB). |
| `bot_empires.py` | Çevrimdışı küresel PvP için 15 bot imparatorluk; denge ölçümü docstring'de. |
| `client_patches.py` | İstemciye uygulanan küçük bayt yamaları. |

## Klasörler

| Klasör | İçinde ne var |
|---|---|
| `assets/` | İstemci SWF'leri ve oyun verisi. En önemlisi `assets/29oct2012/gameSettings_with_fixes.xml`: birimler, eşyalar, görevler, savaş ayarları. `sol_assets_*`: oyuncuların Flash önbelleğinden toplanmış eski asset'ler. |
| `templates/` | Oyun sayfası, kayıt düzenleyici, giriş sayfası, JS (`templates/js/session.js` oturum çerezini yazar). |
| `mods/` | Modlar. `mods/gameRevision_107829_settings` kapalı kalmalı: mini ve mega serileri siler. |
| `turkce/` | Türkçe sürüm: `turkce/mod/turkce` (çeviri modu), `turkce/araclar` (araçlar), `turkce/baslatici`, `turkce/kur.py`. |
| `turkce/araclar/` | `abc.py` (istemcinin AVM2 bayt kodunu söker), `ceviri.py` (çeviri çıkar/kontrol/üret), `sozluk.json`, yazı tipi yamaları, `pvp_yenilgi.py` (eksik PvP yenilgi penceresini üretir). |
| `test/` | Testler (pytest). Ayrıntı aşağıda. |
| `docs/` | Bu belgeler ve denetim raporları. |
| `build-tools/`, `redist/`, `.github/` | Windows kurulum paketi ve GitHub CI (Linux, Python 3.14). |
| `allies/` | Hazır müttefik (komşu) adaları, JSON. |

## Testler

- **Çalıştırma:** depo kökünden `PYTHONPATH=. python -m pytest -q test/`. Windows'ta aynı anda iki pytest çalıştırılamaz. Sebebi `empires-server.py` içindeki `tendo.singleton` kilidi; ayrıntı için bkz. SORUN-COZUM.md.
- **`test/conftest.py`:**
  - Testler metin editörü açamaz.
  - Günlük dosyası ve önbellek geçici klasöre yazılır.
  - Sunucu `configure_app` ile bir kez kurulur. Gerçek kurulumu isteyen test `server` fixture'ını kullanır.
  - Testler depo klasörüne bir dosya yazarsa bütün koşu başarısız sayılır.
- **`test/client_settings.py`:** oyun XML'ini sunucudan bağımsız okur ve beklenen değerleri buradan verir.
- **Testlerin konuları:**
  - `battle_turn_test.py`: istemcinin savaş kodunun Python kopyası; her tur onunla karşılaştırılır.
  - `session_layer_test.py`: AMF üzerinden uçtan uca testler. Yardımcılar: `batch`, `new_save`, `stored`, `raw_record`.
  - `server_setup_test.py`: sunucu kurulumu, Host kontrolü, 500 sayfası.
  - Diğer dosyalar birer modülü test eder.
- **Kalite ölçümü** (beklenen değerin kaynağı, bozma denemeleri): [denetim/test-kalitesi.md](denetim/test-kalitesi.md).

## Belgeler

| Belge | Konu |
|---|---|
| `README.md`, `README.en.md` | Kurulum ve oyuncu için anlatım |
| `docs/DENETIM.md` | Bütün denetimlerin özeti ve düzeltme durumu |
| `docs/denetim/*.md` | Çekirdek ve savaş denetimleri, yeniden denetimler, test kalitesi |
| `docs/denetim/hesap/` | Denetimlerde kullanılan ölçüm betikleri (yeniden çalıştırılabilir) |
| `docs/SORUN-COZUM.md` | Bilinen tuzaklar, hata ve çözümleri |
| `docs/DEVIR.md` | Son durum, açık işler, yeni oturuma devir |

## Git düzeni

- **Depo:** `lahmacunveayran/raisetheempires-tr`, uzak adı `tr`.
- **Ana dal:** `main`; yerelde adı `turkce`.
- **İş akışı:** her iş kendi dalında yapılır. "gönder" denince dal push edilir ve Türkçe bir PR açılır. Birleştirmeyi kullanıcı yapar.
- **Commit ve PR'larda yapay zekâ ibaresi kullanılmaz.**
- **Upstream:** `AcidCaos/raisetheempires`, uzak adı `origin`. Bizim temelimiz upstream'in `a499313` commit'i.
