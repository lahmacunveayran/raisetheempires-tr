# Devir: son durum ve sıradaki işler (6 Kasım 2026)

Bu belge yeni bir oturumun (bulut ya da yerel) işi kaldığı yerden sürdürmesi için yazıldı. Önce [../CLAUDE.md](../CLAUDE.md), [HARITA.md](HARITA.md) ve [SORUN-COZUM.md](SORUN-COZUM.md) okunmalı.

## 1. Dallar

| Dal (GitHub `lahmacunveayran/raisetheempires-tr`) | İçerik | Durum |
|---|---|---|
| `main` | Kullanıcının oyun sürümü. PR #1 ve #2 birleşti. | — |
| `denetim-1` | PR #2'den sonraki bütün test kalitesi işi, sunucu düzeltmeleri, belgeler (aşağıda) | testler geçiyor; **yeni PR açılacak** (PR #2 zaten birleşti) |
| `pr46-yedek-inceleme` | Upstream PR #46'nın dalı `fixes-round-2`, artı bakımcının 3 yorumuna 3 commit (4a6bbbb, 76e315f, b9ccafe) | testleri geçiyor (73); exe denemesi yarım; upstream'e **gönderilmedi** |

Upstream `AcidCaos/raisetheempires`:
- **Birleşenler:** #44 ve #45.
- **Açık:** #46 (yedekler, CSRF, geri alma; bakımcı Natlies'in 3 yorumu var) ve #47 (mini ve mega seriler).
- **Bilgi için:** #49 (xMystico, Ruffle desteği) başka bir katkıcının.

PR #46'nın dalı kullanıcının fork'unda: `lahmacunveayran/raisetheempires`, dal `fixes-round-2`. O fork'a push edilirse PR #46 güncellenir ve Natlies görür.

## 2. `denetim-1`'de ne var (ana dala göre)

1. **Test kalitesi ölçümü ve iki denetim.** Ayrıntı: [denetim/test-kalitesi.md](denetim/test-kalitesi.md).
2. **Sunucu düzeltmeleri:**
   - Titan `<against>` çarpanı.
   - Genişleme anahtarı, enerji eşyası ve enerji doldurma (008865b).
   - `configure_app`.
   - Bozuk bir kayıt (oyuncusu olmayan) artık başka oyuncuların yağma, ziyaret ve yardım çağrılarını düşürmüyor: `get_saves()` onu atlıyor (d676b4b).
3. **Savaş motoru istemciye uyduruldu** (ebc12cc): DoT `<against>`, araştırma hasarı, en az 1 hasar kuralı, CombatChain'in bütün türlere bakması, iyileştirme hedefi.
4. **Yeni test dosyaları:** `server_setup_test.py`, `server_handlers_test.py`, `battle_reward_test.py`, `save_backup_test.py`, `save_migration_test.py`, `save_server_test.py`. Sunucunun kendi çıktısını kopyalayan 8 altın JSON dosyası silindi.
5. **Test yalıtımı:** `server` fixture'ı her testten sonra save.db'yi boşaltıyor (d676b4b). Parçalar birleşince bir testin bıraktığı yarım kayıtlar sonraki testte "başka oyuncu" gibi görünüp 4-5 testi düşürüyordu.
6. **Belgeler:** `CLAUDE.md`, `docs/HARITA.md`, `docs/SORUN-COZUM.md`, bu belge, `docs/denetim/test-kalitesi.md` ve kanıtlar (`docs/denetim/hesap/test-kalitesi/`).

Son doğrulama (6 Kasım, Windows, Python 3.12): bütün test takımı normal, karışık (tohum 7, 42, 3, 99) ve ters sırayla geçti. Sayılar §6'da.

## 3. Yarım kalan işler (öncelik sırasıyla)

### 3.1 Birleşen ama bağımsız denetlenmeyen parçalar (ilk iş)
`denetim-1`'e birleşti ve testleri geçiyor. Ama 2. tur yardımcıları durdurulduğu için bağımsız denetimden geçmedi:
- **Savaş motoru değişiklikleri** (ebc12cc, `battle_engine.py`). Oyunun hesabını değiştiriyor.
  - Bağımsız bir denetçi istemcinin bayt koduyla karşılaştırmalı: `BattleHost.resolveAttack`, `CombatChain.getHitValue`, `UnitItem.getModifier`, DoT tur sonu kodu.
  - Kanıt: `docs/denetim/hesap/test-kalitesi/tur2/savas/`. Oradaki `mut_results.json`'da 66 mutant var: 18 öldü, 46 sağ kaldı, 2 yeniden yazıldı. Ölçüm yarıda kaldı, sağ kalanlar sınıflandırılmadı.
- **Savaş ödülü testleri** (`battle_reward_test.py`). mutmut listesinden 35 mutantın 18'i öldü; kalan 17 sınıflandırılmalı: eşdeğer mi, yalnızca print mi, gerçek boşluk mu. Liste: `tur2/odul/final_full_suite.jsonl`.
- **Kayıt testleri** (`save_*_test.py`). Son commit "YARIM": ortak `server` fixture'ına geçiş yapıldı, testler geçiyor. Kalanlar:
  - denetimin save_engine / save_migration mutantlarının yeniden ölçümü (`tur2/kayit/remut.py`);
  - özet sayılar.

**Yöntem:** her yeni test için fail-to-pass; mutantlar süre sınırlı koşturucuyla (mutmut kullanılmaz). Kurallar: `tur2/ORTAK.md`.

### 3.2 Upstream PR #46: bakımcının yorumları
Natlies'in 3 yorumu (`save_engine.py`):
1. sqlite3 yerine SQLAlchemy kullanılması;
2. `backups.db`'nin `save.db` ile aynı klasörde olması (kaynaktan çalışma, `instance/`, PyInstaller exe);
3. yedek sayısı için komut satırı seçeneği; 85 seviye hilesi elle alınmış yedekleri siliyor.

`pr46-yedek-inceleme` dalında üçü de yapıldı ve testleri var:
- **4a6bbbb:** `backups.db` artık `save.db`'nin yanında; eski yerdeki dosya bir kez taşınıyor, üzerine yazılmıyor.
- **76e315f:** yedekler SQLAlchemy modeliyle tutuluyor (`Backup`, tablo `backups`, aynı sütunlar). Motor bir veritabanı adresinden kuruluyor; eski `backups.db` dosyaları çalışmaya devam ediyor.
- **b9ccafe:** `--max-backups=N` seçeneği (varsayılan 20, 0 = hepsi). Yalnızca otomatik seviye yedekleri siliniyor; bilerek alınanlar hep kalıyor.

**Kalanlar:**
1. Exe denemesi. `tur2/inceleme/exe_check.py` hazır, derleme yarıda kesildi. Exe, kurulu ve taşınabilir düzende çalıştırılıp `save.db` ile `backups.db`'nin nereye yazıldığı gösterilmeli. Ya da PR'a CI'ın eklediği kurulum paketiyle denenmeli.
2. Bağımsız denetim.
3. Kullanıcı onay verince fork'a push (`fixes-round-2`) ve aşağıdaki yanıt.

**Natlies'e yanıt taslağı.** Kullanıcı onay vermeden gönderilmez; commit adları push'tan sonra kontrol edilmeli.

> Thanks for the review, all three points are addressed in the new commits:
>
> **backups.db location** (4a6bbbb): you were right, when running from source save.db is moved into the instance folder but backups.db stayed in MyGamesPath. backups.db now always goes next to the save database that `save_database_path()` picked (source, installed and frozen layouts are covered by tests), and a backups.db left in MyGamesPath by the earlier version is moved once (a copy is kept in backup-save-db, an existing file is never overwritten). I'll also check it with the installer CI attaches to this PR.
>
> **SQLAlchemy** (76e315f): backups are now an SQLAlchemy model (`Backup`, table `backups`, same columns and index as before) on an engine created from a database URL, by default `sqlite:///<folder of save.db>/backups.db`, so a server can point it at another database. Existing backups.db files keep working. I kept it on its own declarative base and engine rather than a Flask-SQLAlchemy bind, so it doesn't depend on how the app is set up; it should be easy to move into your models/alembic setup when that lands — happy to adapt it to whatever structure you prefer.
>
> **Number of backups** (b9ccafe): `--max-backups=N` (default 20, `0` keeps all, documented in SERVERS.md). Backups now record whether they were made automatically (level ups) or on purpose (save editor, cheats, quest commands, seed, deprogress, patches, restores), and only automatic ones are pruned, so the level-85 XP cheat no longer pushes out a backup made before it. Backups from older backups.db files count as made on purpose.

### 3.3 Açık oyun hataları ve kararlar
- **Genişleme satın alınınca bedel alınmıyor** (`buy_expansion_response`). İstemcinin yaptığı:
  - `GMExpansion.buyExpansion`, önce `Player.buyItem(x01, useCash=false)` çağırıyor.
  - Bedel `ExpansionItem.getAmount(cost, scalar) = cost × scalar^n` (n = açık genişleme sayısı − başlangıç genişlemeleri): 5000 × 1,2^n altın ve 10 × 1,005^n xk01.
  - İşin içinde ayrıca `multiRequirementItemInfo` ve `m_discountInfo` (indirim) var; yuvarlama ve indirim doğrulanmadı.
  - Önerilen kod: `tur2/isleyici/try_fixes.py` → `pay_expansion`. Hata testleri: `tur2/isleyici/zz_server_bugs_test.py`.
- **Parası yetmeyen satın alma.** Sunucu nakdi eksiye düşürebiliyor. İstemcinin `Player.buyItem`'ı da kontrol etmiyor; pazar arayüzü zaten ödenebilecek olanı gösteriyor. Değiştirmek istemciden farklı davranmak olur. Karar kullanıcının.
- **Pazara bina koymak** sunucuda TODO ("Can't reserve"). İstemci (`MarketHost`) eşyayı envanterden düşüyor.
- **`/wipe_session` POST** (denetim mutantı #113): dayanak bulunamadı, açık.
- **500 sayfası** `It went wrong` metnini HTTP 200 ile döndürüyor. İstemcinin hangi durumu beklediği belli değil, değiştirilmedi.
- **Sunucu dosyasında** hiç çalışmayan ~25 fonksiyon var: `tur2/isleyici/cov_with_uncovered.txt`.

### 3.4 Kullanıcının bilgisayarında yapılacaklar (bulutta yapılamaz)
- `denetim-1` için açılan yeni PR birleşince:
  1. yerel `turkce`, `tr/main`'den güncellenir;
  2. oyun çalışma kopyası `TurkceOyun\kod` (dal `oyun`) güncellenir: `git merge turkce`.
- **Bundan önce oyun kaydı yedeklenir:** `TurkceOyun\yedekle.py`. Savaş motoru ve satın alma kodu değişti.
- Oyunda denenecekler:
  - bir savaş (hasarlar makul mü);
  - genişleme anahtarı satın alma (F5'ten sonra envanterde mi);
  - enerji eşyası ve enerji doldurma.

## 4. Bulut oturumu için başlangıç metni

Yeni bulut oturumunu `lahmacunveayran/raisetheempires-tr` deposunda, `denetim-1` dalından başlatıp şu metni verin:

```
Bu depo Raise the Empires'ın Türkçe sunucusu. Önce CLAUDE.md, docs/DEVIR.md, docs/HARITA.md ve docs/SORUN-COZUM.md'yi oku; kurallar CLAUDE.md'de (Türkçe ve basit konuş, commit/PR'a yapay zekâ ibaresi yok, GitHub'a göndermeden önce sor, limitim önemli).

Çalıştığın dal: denetim-1. Sıradaki işler docs/DEVIR.md §3'te, şu sırayla:
1) §3.1: birleşen ama bağımsız denetlenmeyen savaş motoru, savaş ödülü ve kayıt testlerini bağımsız bir denetçiye (sonucu söylemeden, kodu vererek) denetlet; sağ kalan mutantları sınıflandır, gerçek boşluklara fail-to-pass kanıtlı test ekle. Yöntem: docs/denetim/test-kalitesi.md ve docs/denetim/hesap/test-kalitesi/tur2/ORTAK.md.
2) §3.3: genişleme bedeli hatasını istemcinin bayt koduyla (turkce/araclar/abc.py) doğrula ve düzelt; doğrulanamayan ayrıntıyı bana yaz.
3) §3.2: pr46-yedek-inceleme dalını bağımsız denetlet; exe/kurulum denemesinin nasıl yapılacağını bana söyle (Windows exe bulutta çalışmaz).
4) Bütün test takımını normal, ters ve karışık sırayla çalıştır (CI Linux'ta Python 3.14 kullanıyor, onu da kontrol et). Sonra belgeleri (docs/DEVIR.md, docs/denetim/test-kalitesi.md, docs/SORUN-COZUM.md) güncelle.
GitHub'a push, PR açma ve upstream'e (AcidCaos/raisetheempires) yorum yazma için önce bana sor. Upstream'e gidecek Natlies yanıt taslağı docs/DEVIR.md §3.2'de.
```

## 5. Teknik notlar (devralan için)

- **Testi çalıştırma:** depo kökünden `PYTHONPATH=. python -m pytest -q test/`. Linux'ta tek-örnek kilidi sorun çıkarmaz. Windows'ta aynı anda tek pytest çalışır; ayrıntı SORUN-COZUM.md'de.
- **Karışık sıra:** `docs/denetim/hesap/test-kalitesi/denetim2/plugins/denetim2_shuffle.py`. Kullanım: `PYTHONPATH=.:<o klasör> SHUFFLE_SEED=7 python -m pytest -p denetim2_shuffle test/`; ters sıra için `SHUFFLE_SEED=reverse`.
- **İstemci kodu:** `python turkce/araclar/abc.py assets/ZGame.109338.swf method <Sınıf> <metot>`. Daha önce sökülmüş parçalar: `docs/denetim/hesap/test-kalitesi/tur1/abc/` ve `denetim2/bytecode/`.
- **Kanıtlardaki yollar:** `<S>` (geçici klasör) ve `<HOME>` yer tutucudur; betikler çalıştırılmadan önce yollar düzeltilmeli.

## 6. Son doğrulama

`denetim-1`, commit d676b4b, 6 Kasım 2026, Windows, Python 3.12. Linux'ta Python 3.14 ile (CI) henüz denenmedi.

| Koşu | Sonuç |
|---|---|
| normal sıra | 420 geçti, 0 hata |
| karışık sıra (tohum 7, 42, 3, 99) | her birinde 420 geçti, 0 hata |
| ters sıra | 420 geçti, 0 hata |
| fail-to-pass: `get_saves` düzeltmesi geri alınınca | yeni test başarısız (beklenen) |
