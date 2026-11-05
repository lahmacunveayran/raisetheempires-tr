# Test Kalitesi Denetimi 2: raisetheempires-pr

Tarih: 2026-11-05. Denetlenen durum: `denetim-1` dalı, HEAD `585fe05` ve üstündeki **commit'lenmemiş çalışma ağacı**. Bu ağaçta 7 değişmiş dosya ve yeni `test/client_settings.py` var.
Denetçi bağımsızdır. `docs/`, commit mesajları ve önceki denetim klasörleri okunmadı (ayrıntı için bkz. §13).

---

## 0. Kısa özet (programcı olmayan sahibi için)

**Genel not: 6 / 10**

Testler "sırf geçsin diye" yazılmış değil. Bunu sayılarla gösterdim. Oyunun **savaş hesabı** için gerçek oyunun (Flash istemcisinin) kurallarını tek tek kopyalayan bağımsız bir model yazılmış. Bu model istemcinin bayt koduyla karşılaştırıldı ve doğru çıktı. Bilerek bozduğum savaş kurallarının çoğunu da testler yakaladı. **Kayıt (save) ve oturum** testleri ise sunucuya gerçek oyunun gönderdiği biçimde (AMF) istek atıyor; yani sadece iç fonksiyonları çağırmakla yetinmiyor.

Zayıf yanlar şunlar:

- **Sunucunun büyük kısmı hiç denenmiyor.** `empires-server.py` içindeki karar noktalarının yalnızca **%25,5**'i test sırasında çalışıyor. 137 fonksiyondan 43'üne hiç girilmiyor; satın alma, pazar, eşya kullanma ve yağma bunlardan bazıları. Buralarda bir hata çıksa testler sessiz kalır.
- **Savaş testleri dar bir durumu kapsıyor.** Kapsanan durum: 1. seviye oyuncu, araştırma yok, iksir/destek eşyası (consumable) yok, kara birlikleri. Araştırma bonusları, zehir gazı gibi her tur hasar veren eşyalar ve isabet/kaçınma eşyaları bozulduğunda testler fark etmedi.
- **Bazı testler "eski çıktıyla aynı mı?" diye bakıyor.** Beklenen değerin nereden geldiği yazılmamış: 16 test hazır dosyayla, 41 test açıklamasız sayılarla karşılaştırıyor. Bunlar bir **değişikliği** yakalar ama mevcut davranış zaten yanlışsa yakalayamaz.
- **Kayıt düzenleyici ve yedekler yalnızca kısmen kontrol ediliyor.** Bir yedeğin içinde nelerin saklandığı ve düzenleyicinin geri yazdığı alanlar denetlenmiyor. "Başka siteden gelen isteği engelle" koruması 13 adresten yalnızca 2'sinde deneniyor.
- **Testler karışık sırayla çalıştırılınca 27–28 test hata veriyor.** Sebep oyunda değil, bir test hazırlığının (fixture) iki kez kurulamaması. Normal sırayla tüm testler her seferinde geçiyor.

Ana sayılar:

| Ölçü | Değer |
|---|---|
| Test sayısı | 230 (hepsi geçiyor; atlanan veya "beklenen hata" yok) |
| Dal (branch) kapsamı, tüm üretim kodu | **%47,8** (861/1800) |
| Mutasyon skoru | rastgele örneklem, eşdeğerler çıkarılınca **370/531 = %69,7** (ham: 370/577 = %64,1). Dosya bazında: savaş %79,2 (141/178), save_engine %70,7 (111/157), sunucunun kayıt/oturum kısmı %65,2 (90/138), kayıt göçü %48,3 (28/58) |
| Elle yapılmış hedefli bozmalar | 25/25 öldürüldü (24 test hatası + 1 zaman aşımı) |
| Kararsızlık (flaky) | 3+3 normal ve 1 ters sıralı çalıştırmada 0 hata. 5 karışık sıralı çalıştırmanın 5'inde de 27–28 kurulum hatası (sıra bağımlılığı). Rastgelelik kaynaklı yanlış alarm olasılığı ≈ 0. |

---

## 1. Kapsam ve yöntem

**Örnekleme.**
- **Tüm testler:** 227 test fonksiyonunun hepsi (parametrelerle 230 test) beklenen değerin nereden geldiğine göre elle sınıflandırıldı (§3).
- **Tam okunanlar:** savaş, kayıt ve eşzamanlılık testlerinin hepsi. Dosyalar: `battle_turn_test.py`, `battle_test.py`, `session_layer_test.py`, `empires_test.py`, `save_actions_test.py`, `state_machine_test.py`, `titan_lab_test.py`, `bot_empires_test.py`.
- **Diğer dosyalar:** her birinin tamamı okundu ama daha hızlı. Dosyalar: quest, quest_trees, megaseries, event_buildings, treasure_vault, slot_machine, bounty_center, client_patches.

**Mutasyon.**
- mutmut 2.5.1'in kendi mutasyon operatörleri kullanıldı (`mutmut.mutate`). Çalıştırma, bu makinede tam koşu yaklaşık 12 saat süreceği için kendi koşturucumla yapıldı (`mut_harness.py`): tohumlu rastgele örneklem alınıyor ve yalnızca testlerin çalıştırdığı satırlardaki mutantlar seçiliyor.
- Bütün kapsam için bir tahmin de verildi: hiç çalışmayan satırlardaki mutantlar öldürülemez sayıldı.
- Buna ek olarak, testlerin korumayı iddia ettiği davranışlara **25 hedefli mutant** elle yapıldı (`targeted_mutants.py`).

**Ortam.**
- Python 3.12 (`venv312`), pytest, coverage 7.6, mutmut 2.5.1.
- Bütün mutasyon ve güvenilirlik deneyleri `git worktree` kopyasında (`denetim2\wt`) yapıldı. Gerçek depoya hiç yazılmadı.
- Her pytest koşusu `test/conftest.py`'yi yükledi (metin editörü kapalı).

**Ölçülen / çıkarılan.** Her bulguda **[Ö]** ölçülen (komutla elde edilen sayı), **[Ç]** çıkarım (kod okumasıyla varılan yargı) olarak işaretlendi; yanında güven düzeyi var.

---

## 2. Ölçülen sayılar ve komutlar

Bütün komutlar depo kökünde ya da worktree'de çalıştırıldı. Ortam değişkenleri: `PYTHONPATH=<kök>`, `PYTHONUTF8=1`.

```
# temel koşu
venv312\Scripts\pytest.exe -q -p no:cacheprovider                         -> 230 passed (31-40 s)
# dal kapsamı (kendi başlatıcım: tekil argv[0], tek-örnek kilidiyle çakışmasın diye)
coverage run --branch -m ... denetim2\run_pytest_denetim2.py -q -p no:cacheprovider
coverage json -o denetim2\coverage.json ; python denetim2\cov_summary.py  -> coverage_branch_summary.txt
# güvenilirlik (3 normal, 1 ters, 5 karışık sıra, her dosya tek başına; sızıntı eklentisi açık)
powershell -File denetim2\reliability.ps1                                -> reliability.txt, leaks_*.txt
# mutasyon (sırayla, yalnızca worktree'de)
powershell -File denetim2\mutation_runs.ps1                              -> mut_*.json / mut_*.log
python denetim2\mut_summary.py mut_battle_engine.json mut_save_engine.json mut_server_save.json mut_save_migration.json --survivors
python denetim2\mut_recheck.py --wt denetim2\wt --json mut_battle_engine.json --json mut_save_engine.json --json mut_server_save.json --json mut_save_migration.json
python denetim2\mut_survivors.py --list                                  -> mut_survivors.txt (E/G sınıflaması, skorlar)
python denetim2\targeted_mutants.py --wt denetim2\wt                     -> targeted_mutants.json
# worktree: git -C <repo> worktree add --detach denetim2\wt HEAD ; commit'lenmemiş 8 dosyayı kopyala ; sonunda git worktree remove --force
# beklenen değer sınıflandırması
python denetim2\oracle_siniflandirma.py <repo>                           -> oracle_siniflandirma.txt
# kasa testinin şans eseri başarısız olma ihtimali
python denetim2\vault_flake_odds.py   (depo klasöründen)
```

### 2.1 Dal kapsamı [Ö, güven yüksek]

| Dosya | Satır | Dal |
|---|---|---|
| battle_engine.py | 667/900 (%74,1) | 228/374 (**%61,0**) |
| empires-server.py | 880/1749 (%50,3) | 185/726 (**%25,5**) |
| save_engine.py | 154/183 (%84,2) | 21/34 (%61,8) |
| save_migration.py | 62/85 (%72,9) | 17/28 (%60,7) |
| state_machine.py | 149/210 (%71,0) | 36/86 (%41,9) |
| mod_engine.py | 47/107 (%43,9) | 13/46 (%28,3) |
| init_settings.py | 13/39 (%33,3) | 0/22 (%0) |
| quest_engine.py | 302/363 (%83,2) | 77/120 (%64,2) |
| küçük modüller (slot_machine, treasure_vault, titan_lab, quest_trees, megaseries, event_buildings, bounty_center) | %90–100 | %80–100 |
| **TOPLAM** | **3502/5002 (%70,0)** | **861/1800 (%47,8)** |

Hiç çalışmayan önemli bölgeler:

**empires-server.py:** 137 üst düzey fonksiyonun 43'üne hiç girilmiyor. Örnekler: `buy_item_response`, `buy_expansion_response`, `place_market_order`, `use_item_response`, `pillage_response`, `load_world_response`, `tend_ally_response`, `world_name_response`.

**battle_engine.py:**

| Satırlar | Ne yapıyor |
|---|---|
| 202-211 | `apply_dot_damage` (her tur hasar) |
| 258-295 | `handle_win`'in istila ve komşu dalları |
| 349-354 | isabet araştırması |
| 654-700 | `next_campaign_response` |
| 714-728 | `get_mastery_units` |
| 800-816 | `get_reward_multiplier` |
| 912-929 ve 1008-1022 | `assign_consumable_response`'ın bir kısmı |

**save_engine.py:**

| Satırlar | Ne yapıyor |
|---|---|
| 135-146 | eski `save.db`'yi `instance/`'a taşıma |

**save_migration.py:**

| Satırlar | Ne yapıyor |
|---|---|
| 38-55 ve 94-115 | göç adımları |

### 2.2 Güvenilirlik [Ö, güven yüksek]

| Koşu | Sonuç |
|---|---|
| normal sıra ×3 (ve önceden ×3) | 230 geçti, her seferinde |
| ters sıra (`denetim2_shuffle.py`, `SHUFFLE_SEED=reverse`) | 230 geçti |
| karışık sıra, tohumlar 11 / 22 / 33 / 44 / 55 | 202 / 202 / 203 / 202 / 202 geçti; **28 / 28 / 27 / 28 / 28 hata** |
| her test dosyası tek başına (16 dosya) | hepsi geçti |
| test sonrası canlı kalan iş parçacığı | 0 |
| ağ çağrısı (socket connect/bind) | 0 |
| depo klasörüne yazılan dosya | her koşuda `log.txt`; ilk koşuda `cache/directory.cache` ve `cache/mods.config.cache` |

Karışık sıradaki hataların hepsi `session_layer_test.py` kurulumunda çıkıyor:
`RuntimeError: A 'SQLAlchemy' instance has already been registered on this Flask app`. Ayrıntı için bkz. B-O1.

---

## 3. Beklenen değerin kaynağı (oracle kalitesi)

Sınıflar:
- **I1:** istemcinin bağımsız modeli (bayt kodundan) ya da XML'den türetilmiş, türetmesi testte yazılı.
- **I2:** girdiden veya açıkça yazılmış bir kuraldan çıkıyor.
- **M:** türetmesiz sabit sayı.
- **S:** anlık görüntü / altın ana (kodun önceki çıktısı).
- **C:** döngüsel (beklenen değer test edilen kodla ya da ondan kopyalanmış bir modelle hesaplanıyor).
- **W:** zayıf (neredeyse hiç başarısız olamaz).

[Ö sayım; sınıflandırma Ç, güven orta-yüksek]

| Dosya | I1 | I2 | M | S | C | W |
|---|---|---|---|---|---|---|
| battle_test.py | 0 | 6 | 8 | 15 | 0 | 0 |
| battle_turn_test.py | 30 | 7 | 0 | 0 | 0 | 0 |
| bot_empires_test.py | 2 | 9 | 1 | 0 | 2 | 1 |
| bounty_center_test.py | 0 | 2 | 3 | 0 | 0 | 0 |
| client_patches_test.py | 0 | 2 | 0 | 0 | 0 | 0 |
| empires_test.py | 0 | 17 | 8 | 1 | 0 | 2 |
| event_buildings_test.py | 0 | 5 | 7 | 0 | 0 | 0 |
| megaseries_test.py | 0 | 1 | 0 | 0 | 3 | 1 |
| quest_test.py | 0 | 0 | 6 | 0 | 0 | 0 |
| quest_trees_test.py | 0 | 6 | 0 | 0 | 5 | 1 |
| save_actions_test.py | 0 | 13 | 0 | 0 | 0 | 0 |
| session_layer_test.py | 0 | 35 | 0 | 0 | 0 | 1 |
| slot_machine_test.py | 0 | 2 | 1 | 0 | 0 | 1 |
| state_machine_test.py | 0 | 1 | 2 | 0 | 0 | 0 |
| titan_lab_test.py | 1 | 9 | 3 | 0 | 0 | 0 |
| treasure_vault_test.py | 0 | 3 | 2 | 0 | 0 | 2 |
| **TOPLAM (227)** | **33 (%15)** | **118 (%52)** | **41 (%18)** | **16 (%7)** | **10 (%4)** | **9 (%4)** |

Ayrıca aranıp bulunmayanlar [Ö, grep + okuma]:
- `pytest.skip`, `xfail` veya `skipif` yok.
- `approx` veya toleranslı karşılaştırma yok.
- Exception'ı yutan `try/except` yok.
- Test edilen birimin yerine geçen bir mock yok. `monkeypatch` yalnızca saat, rastgele sayı tohumu, dosya yolu ve kayıt veritabanı için kullanılıyor.

**Yalnızca durum kodu kontrolü ve 500 sayfası [Ç, güven yüksek].**
- 500 işleyicisi `empires-server.py:3204-3213` içinde ve `return 'It went wrong'` döndürüyor; durum 500, içerik türü text/html.
- Ağ geçidi testleri `session_layer_test.py` içindeki `batch()` yardımcısıyla `content_type == "application/x-amf"` kontrol ediyor ve yanıtı AMF olarak çözüyor.
- Rota testleri 302/400/403/204 bekliyor.
- Hiçbir durum kontrolü 500 sayfasıyla geçemez.

---

## 4. İstemci referans modelinin bayt koduna karşı kontrolü [Ç, güven yüksek]

`turkce/araclar/abc.py` ile `ZGame.109338.swf` sökülerek `battle_turn_test.py` içindeki model karşılaştırıldı.

**Tutarlı çıkan kısımlar:**

| Bileşen | İstemcideki davranış |
|---|---|
| `ClientRandom` | ZGameRandom: iki MWC üreteci. `m_z = 36969*(z&65535)+(z>>16 & 65535)`, w için 18000 kullanılıyor. Sonuç `((z<<16)+w) & 0xFFFFFFFF` (uint). `float = roundTo(r/uint.MAX_VALUE, 3)`: 3 basamakta kesme. `randBetween = f*(b-a)+a`. |
| `client_roll` | getDiceRoll: saldıran zayıfsa WEAK_ROLL, savunan zayıfsa STRONG_ROLL, değilse `randBetween(0,1)`. |
| `find_best_unit` / `client_ai` | -1'den başlıyor; ölü veya sersemlemiş birlik atlanıyor. Kesin `>` ya da değer ≥0 iken eşitlik. Seçim `int(Math.round(r*(n-1)))`. FocusFire hiç açılmıyor (`shouldFocusFire` hiç çağrılmıyor). FindBestDefendingUnit'te AgainstAttackers ilkini tutuyor. Oran < `combatAISwitchRatio` 0.5, geçiş zarı < `combatAISwitchPercent` 0.2. |
| `client_damage` | GetAttackingDamage: `base*(3*atk + def_cur)/(3*cur + atk)/100*def.getAttackStrength`. Sonra değiştiriciler ve roundTo 3. GetDamageBase'de `empire_combat_damage` deneyi kayıtta yok, bu yüzden artış 0 ve en az 25. |
| resolveAttack | İsabet: zar ≥ direct (`combatAllowMiss`). AI'da sıyırma var (`combatAICanMiss` false). Kritik: zar ≠ STRONG_ROLL ve zar ≥ crit; AI için 10. seviye altında `combatAICanCritical`, üstünde deney değeri 2 = ENABLED. Ardından ceil. Oyuncu saldırısında `0 < str - dmg ≤ 1` ise +1. |
| getModifier | Birliğin sahip olduğu ilk `<against>` geçerli, yoksa 1. Bu, çalışma ağacındaki `battle_engine.py:1075-1078` değişikliğiyle uyumlu. |
| XML sabitleri | glancing 0.10, critical 1.5, base 25, tier increment `0,0,5,3,5` |

**Modelde olmayan kurallar (bkz. B-D3):**
- `damage - upgradeDamage == 0` ise +1 kuralı.
- "weaker" işaretli birlikler.

Bunlar test havuzundaki (`U01,U04,U05,V03,V61,V62,ML11,PU3`, 1. seviye, araştırma yok) birliklerle tetiklenemiyor.

---

## 5. Mutasyon testi

### 5.1 Rastgele mutantlar (mutmut 2.5.1 operatörleri) [Ö, güven yüksek; genelleme Ç, güven orta]

**Yöntem.**
- Her kapsam için mutmut'un ürettiği mutantlardan, tüm test takımının çalıştırdığı satırlardakiler arasından tohumlu (seed 1) rastgele bir örneklem alındı.
- Her mutant önce dosyanın kendi testleriyle koşturuldu (`mutation_runs.ps1`).
- Sağ kalanlar ikinci kez **bütün test takımıyla** koşturuldu (`mut_recheck.py`). Yalnızca iki yavaş bot dengesi testi dışarıda bırakıldı; bunlar `bot_empires`'ın kendi modelini ölçüyor.
- Kalan her mutant elle **E** (eşdeğer, gerekçesiyle) ya da **G** (gerçek boşluk) olarak sınıflandı (`mut_survivors.py`; liste `mut_survivors.txt`).
- **Skor = öldürülen / (örneklem − eşdeğer).**

| Kapsam | Tüm mutant | Çalışan satırlarda | Örneklem | Dosya testleri öldürdü | Tüm takım ek öldürdü | Eşdeğer | Gerçek boşluk | **Skor** (95% Wilson) | Tüm kapsam tahmini |
|---|---|---|---|---|---|---|---|---|---|
| battle_engine.py | 2201 | 1584 | 200 | 141 | 0 | 22 | 37 | **141/178 = %79,2** (72,7–84,5) | %57,0 (52,3–60,8) |
| save_engine.py | 208 | 167 | 167 (hepsi) | 106 | 5 | 10 | 46 | **111/157 = %70,7** (63,2–77,3) | %56,8 (50,7–62,0) |
| empires-server.py, kayıt/oturum satırları (100-213, 301-308, 523-604, 896-1003, 3205-3264) | 387 | 352 | 150 | 90 | 0 | 12 | 48 | **90/138 = %65,2** (57,0–72,7) | %59,3 (51,8–66,1) |
| save_migration.py | 260 | 163 | 60 | 28 | 0 | 2 | 30 | **28/58 = %48,3** (35,9–60,8) | %30,3 (22,5–38,1) |
| **Toplam** | | | **577** | 365 | 5 | 46 | 161 | **370/531 = %69,7** | |

"Tüm kapsam tahmini" = skor × (çalışan satırlardaki mutant / tüm mutant). Hiç çalışmayan satırlardaki mutantlar öldürülemez.

**Eşdeğer mutantların kanıtları** (hepsi `mut_survivors.py` içinde):

- **Yalnızca bir `print()` argümanı değişiyor** (21). Örnekler: battle_engine.py:119, 413, 956, 1096, 1102, 1122, 1437, 1453; save_engine.py:149, 281; sunucu 152, 202, 211, 528, 555, 913, 940, 996. Bu çıktılar ne yanıta ne kayda giriyor.
- **battle_engine.py:**
  - **:61 `init_seed`:** yalnızca 123. ve 139. satırdaki print'lerde kullanılıyor.
  - **:546 `fleet_name = "fleet1_"…`:** i = 0 iken while döngüsünün ikinci koşulu aynı adı sınıyor; ilk değer döngüde eziliyor.
  - **:508 `session["battle"][1] is None` → `[2]`:** savaş demeti yalnızca 513, 521 ve 696. satırlarda ve sunucunun 2959. satırında kuruluyor. Hiçbir durumda [0] ve [2] None iken [1] dolu değil.
  - **:950 "AI tried" işareti:** `active_consumables`'ın her okunuşu önce hedefi karşılaştırıyor (1170, 1177, 1200, 173-185, 1473/1478). "AI tried" hiçbir hedefle eşleşmediği için bu kayıt hiç okunmuyor.
  - **:1154 komşuluk tablosunun köşegeni:** `unit_1 == unit_2` durumunda fonksiyon tabloya gelmeden, 1149. satırda 0 döndürüyor.
  - **:1113 `-di` varsayılanı:** XML'de `chipFactor`'lü 4 consumable var; dördünde de `di` tanımlı.
  - **:922:** `-target == 'enemy'` koşulu üretim kodunda iki kez yazılmış; mutant kopyayı değiştiriyor.
- **Yanlış-değer eşdeğerliği** (6): `task = None` → `""` (battle_engine.py:485), `targeted = False` → `None` (902), `crash_log_editor = None` → `""` (sunucu 3217), `SESSION_COOKIE_HTTPONLY = None` (werkzeug yalnızca `if httponly` diye bakıyor) vb. Hepsinde iki değer de "yanlış" sayılıyor.
- **save_engine.py:**
  - **:123 `deepcopy` → `copy`:** `store_backup` yedeği hemen, 83. satırda pickle'lıyor.
  - **:269-276 `converted` sayacı** (4): sayaç yalnızca yazdırılıyor; `if converted` yine doğru kalıyor.
  - **:252 `g.pop`:** `guarded_call` her çağrıda yeni bir liste kuruyor [Ç].
- **Sunucu:**
  - **191:** iki boş host da reddediliyor.
  - **966:** `logger=` yalnızca loglamayı etkiliyor.

**Kontrol:** "E" diye sınıflanan 46 mutantın hiçbiri tüm takımla da öldürülmedi. Bu, sınıflamayla tutarlı.

**Gerçek boşlukların dağılımı** (her birinin gerekçesi `mut_survivors.txt` içinde):

- **battle_engine (37):**
  - Consumable / destek eşyaları (19): isabet, kaçınma, DoT, kalkan, süre, "all" türü, AI'ın ikinci hedefli çağrısı.
  - Kampanya ustalığı / tekrar oynama / `has_battle_context` (7): `len > 3` → `> 4` değişikliği bile fark edilmedi.
  - Yanıtın `metadata` ve `newPVE` alanları (3).
  - Kayıp ödülünde nadir kaynak türleri (3).
  - İstila zaferi dalı, 'D' kampanya haritaları, görev filtresi, 1 hasar sınırı, görev ilerleme adı (5).
- **save_engine (46):**
  - Yedek içeriği ve meta verisi (26): BACKUP_KEYS, list_backups alanları, zaman damgaları.
  - `save_database_uri` (6): testler kendi URI'lerini veriyor, gerçek URI hiç sınanmıyor.
  - `validate_save` (5): "ve" → "veya" ve `blank_allowed` dalları.
  - `_save_id` önek kesimi (4).
  - crash_log ve logger (5).
  - **Döngüsel kontrol:** `MAX_BACKUPS = 20 → 21` sağ kaldı. Sebep: `empires_test.py:414-420` beklenen sayıyı `backup_db.MAX_BACKUPS`'ın kendisinden alıyor.
- **Sunucu (48):**
  - Kayıt düzenleyici sayfasının içeriği ve yazdıkları (27): görev listeleri, battle/fleets/population, `saved`, profilePic, yedek mesajı.
  - **Site dışı istek koruması** (4 mutant): 13 yol önekinden yalnızca 2'si test ediliyor. Test edilmeyenler arasında `/gazillionaire`, `/deprogress`, `/complete_quest/`, `/chooseavatar/` var.
  - Asset önekleri (6).
  - **500 işleyicisinin kaydı:** `@app.errorhandler(500)` → `501` değişikliği sağ kaldı; testler `server_error_page()`'i doğrudan çağırıyor.
  - **`@transactional_session` tamamen silinince** de testler geçti. `guarded_call` dışında patlayan bir istek (örneğin bozuk AMF gövdesi) sınanmıyor.
  - Ruffle ağ geçidi yolu `/127.0.0.1flashservices/gateway.php`.
  - 403 gövdesi, yönlendirme hedefi, çerez bayrağı, form boyut sınırı.
- **save_migration (30):**
  - 0.08a adımının koyduğu deney değerleri (17).
  - 0.02a adımının genişleme listesi ve görev sıfırlaması (10).
  - 0.04a adımı hiç sınanmıyor (2).
  - 0.07a sürümü (1).

**Yöntem notu:** Koşturucu, çok satırlı ifadelerde mutantın metnini bazen ifadenin ilk satırından gösteriyor. Örneğin save_engine #202'nin gerçek değişikliği 286. satırdaki `and` → `or`. Bunu mutantı yeniden üretip diff alarak doğruladım. Durum sayımı ve sınıflama bundan etkilenmiyor.

### 5.2 Hedefli mutantlar [Ö, güven yüksek]

Betik: `targeted_mutants.py`. Her mutant tek bir metin değişikliği ve değiştirilen metnin dosyada tam olarak bir kez geçtiği doğrulandı. Her biri için, o davranışı koruduğunu iddia eden testler koşturuldu.

| Kimlik | Bozulan davranış | Sonuç (ilk düşen test) |
|---|---|---|
| B1 | `as3_round` → Python `round` (yarımları çifte yuvarlıyor) | öldü: `test_ai_attacks_the_most_dangerous_unit` |
| B2 | `against` için ilk-eşleşme `break`'i kaldırıldı | öldü: `test_only_the_first_matching_against_of_a_power_counts` |
| B3 | "1 güçte bırakmama" kuralı kapatıldı | öldü: `test_the_battles_played_here_are_the_engines` |
| B4–B9 | STRONG_ROLL da kritik sayılıyor / 3 basamakta kesme yok / sıyırma 0.15 / AI geçiş yüzdesi 0.25 / AI oran sınırı `<=` / kritik çarpanı 1.4 | hepsi öldü: `test_turns_follow_the_client` |
| B10 | araştırma gücü `ceil` ile yuvarlanıyor | öldü: `test_research_strength_is_rounded` |
| S1 | `lock.acquire()` yok | öldü, ama **yan etkiyle**: alınmamış kilidin `release()`'i hata veriyor |
| **S1b** | kilit tamamen yok (acquire de release de) | öldü: `test_overlapping_requests_of_one_save_wait_for_each_other` |
| S2 / S3 | başarısız çağrının değişiklikleri geri alınmıyor / diğer kayıtlar yine de yazılıyor | ikisi de öldü (session_layer'daki başarısız çağrı testi) |
| S4 | `"localhost" in host` (DNS rebinding) | öldü: `test_answers_only_ip_addresses_and_localhost` |
| S5 | Origin başlığına bakılmıyor | öldü: `test_cross_site_requests_to_save_changing_routes_are_blocked` |
| S6 | düzenleyici geçersiz `user_object` yazıyor | öldü: `test_save_editor_writes_nothing_of_an_invalid_user_object` |
| S7 | kaydedilemeyen değer çağrıda yakalanmıyor | öldü |
| S8 | MAX_BACKUPS + 1 yedek tutuluyor (SQL) | öldü: `test_create_backup_keeps_save_small_and_bounded` |
| S9 | dünya adı sayfadaki script'i kapatabiliyor | öldü: `test_world_names_cannot_end_the_home_page_script` |
| S10 | pickle kontrolü ters çevrildi | öldü: `test_pickled_saves_are_converted_once` |
| S11 | kilit hiç bırakılmıyor | zaman aşımı (240 s), öldü sayıldı |
| S12 | asset istekleri kaydı yüklüyor | öldü: `test_asset_requests_skip_server_side_session` |
| S13 | iç içe yedekler ters sırayla taşınıyor | öldü: `test_move_nested_backups_keeps_order` |
| S14 | düzenleyici `save_version`'ı güncellemiyor | öldü: `test_save_editor_takes_an_old_backup_without_battle_fleets_and_population` |

**Sonuç: 25/25.**
- Testlerin açıkça korumayı iddia ettiği davranışlarda hata yakalama gücü yüksek.
- Rastgele mutantların sağ kaldığı yerler, testlerin hiçbir iddiada bulunmadığı yerler (bkz. §6).

---

## 6. Bulgular (önem sırasıyla)

Kritik bulgu yok: korunması en önemli davranışlar (kayıt kilidi, başarısız çağrının geri alınması, kayıt doğrulama, Host ve Origin kontrolü, savaş zarı ve hasar formülü) hedefli mutantlarla bozulduğunda testler yakaladı (bkz. §5.2).

### Yüksek

**B-Y1. Sunucu dosyasının çoğu test edilmiyor.** [Ö, güven yüksek]
- `empires-server.py`'nin dal kapsamı 185/726 = %25,5. 137 fonksiyondan 43'üne hiç girilmiyor.
- Para veya kaynak harcayan işleyicilerin hiçbiri çalışmıyor: `buy_item_response`, `buy_expansion_response`, `place_market_order`, `use_item_response`, `pillage_response`.
- Bu bölgelerdeki her mutant tanım gereği "sağ kalır". Bölgelerin seçimi §5'teki kapsam dışı tahmininde var.
- *Düzeltme:* Her işleyici için `session_layer_test.py`'deki `batch()` ile AMF üzerinden en az bir test yazılmalı.
  - Beklenen değer XML'den alınmalı. Örneğin satın almada `gameSettings_with_fixes.xml` içindeki `<item ... cost>` alanı okunur; testte "nakit = önceki − XML fiyatı, envanter +1" kontrol edilir.
  - Yetersiz para gibi hata yolları da ayrıca test edilmeli: "hiçbir şey değişmedi" ve yanıt AMF hatası.

**B-Y2. Savaş hesabı testi dar bir yapılandırmayla sınırlı.** [Ö mutantlar; Ç kapsamın yorumu, güven yüksek]
- `battle_turn_test.py:155` `test_turns_follow_the_client` güçlü bir test: 25 rastgele savaş, 300'den fazla tur, her turda birlik, zar, güç ve tohum kontrol ediliyor.
- Ama yapılandırma hep aynı: havuz `POOL` 8 birlik, 1. seviye, `research = {}`, hiç consumable yok, gemi veya uçak yok, oyuncu seviyesi hep 10'un altında.
- Sağ kalan mutantlar bu boşluğu doğruluyor:
  - `battle_engine.py:69` `crit -= accuracy` → `crit += accuracy`
  - `:42` `("ally", …)` → `("XXallyXX", …)` (isabet, kaçınma ve kalkan hedefi)
  - `:173` ve `:181` her tur hasarın hedef seçimi
  - `:192` consumable süresi `tries - 1` → `tries - 2`
- Satır 202-211 (DoT) ve 349-354 (isabet araştırması) hiç çalışmıyor.
- *Düzeltme:* Aynı istemci modeli, istemcinin `Battle.onUnitDamageFromConsumable`, `getAccuracy`/`getEvasion` ve DoT tur sonu kodundan genişletilmeli. Rastgele savaşlara şunlar eklenmeli:
  - `research` seviyeleri (XML `<upgrade>`),
  - consumable'lar (isabet, kaçınma, kalkan, DoT),
  - seviye ≥ 10 (AI kritiği deney değeriyle),
  - gemi ve uçak birlikleri.
- Her turda aynı alanlar ve ayrıca kalan consumable süreleri kontrol edilmeli.

**B-Y3. Anlık görüntü ve türetmesiz sabitler doğruluğu değil, değişmezliği ölçüyor.** [Ç, güven yüksek]
- `battle_test.py:82-140`: `init_battle` sonucu `friendlies_first_quest.json`, `baddies_second_quest.json` gibi dosyalarla karşılaştırılıyor (15 test). Bu dosyalar sunucunun kendi eşya sözlüklerinin dökümü.
- `empires_test.py:337` vb. `init_user.json`: sunucunun kendi yeni kaydı.
- `battle_test.py:318/325`: `[120, 170, 150]` ve `[116, 170, 147]` hiçbir türetme olmadan yazılmış.
- Toplam 16 S ve 41 M test var. Bunlar regresyonu yakalar. Ama değer baştan yanlışsa yanlışı "doğru" diye kilitler.
- *Düzeltme:*
  - `init_battle` için beklenen birlikler, testte quest XML'inden (`<task _action="fight" _item=…>` → `baddie -item`) okunup `lookup_item_by_code` olmadan, ElementTree ile türetilmeli. `client_settings.py` bunu zaten yapıyor.
  - Şarapnel değerleri (`[116, 170, 147]`) istemcinin `ChipDamageManager.getDamage = ceil(uniqueNumber*chipFactor*di/100)` formülüyle ve XML'deki `-chipFactor` / `-di` ile testte hesaplanmalı.
  - `init_user.json` kontrolü yerine, yeni kullanıcının XML'deki `<startingResources>`/başlangıç eşyalarıyla örtüştüğü kontrol edilmeli.

### Orta

**B-O1. Sıra bağımlılığı: `session_layer_test.py`'nin `server` fixture'ı ikinci kez kurulamıyor.** [Ö, güven yüksek]
- `session_layer_test.py:32-42`:
  ```
  @pytest.fixture(scope="module")
  …
  empires_server.db.init_app(app)
  …
  yield app
  app.session_interface = original_interface
  ```
- Teardown yalnızca `session_interface`'i geri koyuyor. `db` ve `sess` uygulamada kayıtlı kalıyor.
- Testler karışık sırayla çalışınca modül fixture'ı yeniden kuruluyor. 5 tohumun 5'inde 27-28 test `RuntimeError: A 'SQLAlchemy' instance has already been registered` ile hata verdi.
- Ayrıca global `app`'in durumu (uzantılar, `_got_first_request = False` hilesi) testler arasında paylaşılıyor.
- *Düzeltme:* Kurulum `if "sqlalchemy" not in app.extensions:` ile korunmalı, ya da daha iyisi aşağıdaki B-O2'deki gibi her modül için yeni bir uygulama üreten `create_app()` kullanılmalı. Teardown'da `app.extensions` eski haline getirilmeli. `pytest-randomly` veya `-p denetim2_shuffle` ile CI'da bir karışık koşu eklenmeli.

**B-O2. Fixture, `__main__` kurulumunu elle kopyalıyor; gerçek kurulum test edilmiyor.** [Ç, güven yüksek]
- Fixture (`session_layer_test.py:33-41`) `db.init_app`, `sess.init_app` ve `AssetSkippingSessionInterface` kurulumunu elle yazıyor.
- Gerçek sunucu bunları `empires-server.py:3268` ve sonrasındaki `if __name__ == '__main__':` bloğunda yapıyor. Orada `KnownHostsOnly` (satır 3281) ve Socket.IO da kuruluyor.
- `__main__` değişirse (sıra, eksik bir ara katman) testler fark etmez. `KnownHostsOnly`'nin uygulamaya gerçekten takıldığı da test edilmiyor; yalnızca sınıfın kendisi test ediliyor.
- *Düzeltme:* Kurulum `configure_app(app)` gibi bir fonksiyona taşınmalı; `__main__` ve fixture onu çağırmalı. Bir test `app.wsgi_app` zincirinde `KnownHostsOnly` olduğunu ve `Host: evil.example` ile 403 döndüğünü kontrol etmeli.

**B-O3. Tohumlanmamış rastgelelik ve koşullu (kendine bakan) kontroller.** [Ö + Ç, güven yüksek]
- `slot_machine.py:65` ve `treasure_vault.py:112`'de `random.choices` tohumsuz kullanılıyor.
- `slot_machine_test.py:46-49` ve `treasure_vault_test.py:93-96`:
  ```
  if loot["handler"] == "addLootToInventory":
      assert items(user)[loot["payload"]["code"]] == loot["payload"]["quantity"]
  else: …
  ```
  Kodun kendi döndürdüğü ödülü kontrol ediyor. Yanlış ödül tablosu, yanlış ağırlık ya da tablonun dışından bir ödül fark edilmez.
- `treasure_vault_test.py:107-115` tüm kaynak ödüllerini tek bir `"res"` sayıyor ve `len(seen) >= len(item kodları)` kontrol ediyor. "res" de sayıldığı için **bir eşya hiç çıkmasa bile test geçer** (bir eksik sayım).
- Şans eseri başarısız olma ihtimali ≈ 0 (`vault_flake_odds.py`, 20000 simülasyon). Yani sorun kararsızlık değil, zayıflık.
- *Düzeltme:*
  - `monkeypatch.setattr(random, "choices", …)` ile belirli bir ödül seçtirilmeli; envanter veya kaynak değişimi XML `<loot>` tablosundan hesaplanmalı.
  - Kapsama testinde `seen` kodlarla tutulmalı ve `set(item kodları) <= seen` kontrol edilmeli.
  - Ağırlıklar için sabit tohumla 10 000 çekilişte gözlenen oranın XML ağırlığına yakın olduğu kontrol edilmeli. Ağırlıkların hesaplandığı tek kaynak XML olmalı.

**B-O4. Kayıt dosyası taşıma ve kayıt göçü (migration) adımları hiç denenmiyor.** [Ö, güven yüksek]
- Eski `save.db`'yi `instance/`'a taşıyan kod (`save_engine.py:135-146`) çalışmıyor.
- `save_migration.py` içinde 38-55 ve 94-115 satırları çalışmıyor.
- Bu kodlar kullanıcının eski kaydına dokunuyor. Hata olursa kayıt kaybı riski var.
- *Düzeltme:*
  - `tmp_path` içinde eski düzende bir `save.db` (ve `my_games_path()` monkeypatch) hazırlanmalı. `save_database_uri` çağrıldıktan sonra dosyanın taşındığı, içeriğin bayt bayt aynı kaldığı ve eski yolun kalmadığı kontrol edilmeli.
  - Her göç adımı için v(n-1) biçiminde küçük bir kayıt dosyası eklenmeli; beklenen v(n) alanları göçün belgelenmiş kuralından elle yazılmalı.

**B-O5. Savaş ödülü, görev ilerlemesi ve yanıt alanları kontrol edilmiyor.** [Ö mutantlar, güven yüksek]

Sağ kalan mutantlar:

| Satır | Mutasyon | Ne kontrol edilmiyor |
|---|---|---|
| `battle_engine.py:124` | `if damage > 0:` → `> 1` | 1 hasarlık vuruşun ödülü |
| `:126` | `"battleDamage"` → `"XXbattleDamageXX"` | görev ilerlemesi |
| `:32` | `meta = {"newPVE": 0}` → `1` | yanıt meta alanı |
| `:484` | açık görev süzgeci `== False` → `== True` | görev görevinin seçimi |
| `:245` | tekrar ödülü sınırı `<=` → `<` | a = 100 sınırı |
| `:247` | `lambda a: 0` → `lambda a: None` | tekrar oynamada eşya ödülü |

- *Düzeltme:*
  - `battle_complete_response`'ın `meta` ve oturumdaki görev ilerlemesi kontrol edilmeli: görevin `_count` değeri hasar kadar artmalı.
  - Tam 1 hasarda ödül `getCoinAmount` formülüyle hesaplanmalı.
  - Tekrar oynamada a = 100 ve a = 101 için ödül `ceil(a*m)` / `max(a*m, 100)` ile elle hesaplanmalı (`combatReplayRewardMinimum` XML'den okunmalı).

**B-O6. Site dışı istek (CSRF) koruması 13 yol önekinin yalnızca 2'si için test ediliyor.** [Ö: mutantlar #60, #61, #65, #68; güven yüksek]
- Önekler `empires-server.py:167-169` içinde, `SAVE_CHANGING_PATH_PREFIXES`'ta tanımlı.
- `empires_test.py:378-382` yalnızca `/wipe_session` ve `/save-editor` yollarını deniyor.
- Listeden `/gazillionaire`, `/deprogress`, `/complete_quest/` veya `/chooseavatar/` silinse testler bunu fark etmiyor.
- *Düzeltme:*
  - Kayıt değiştiren rotaları test içinde elle listeleyin. `app.url_map`'ten okumayın, yoksa test kendini kontrol eder (döngüsel).
  - Her rota için `Referer: https://evil.example/` başlığıyla istek gönderip 403 bekleyin.
  - Ek olarak `app.url_map`'teki her rotanın ya bu listede ya da açıkça "kaydı değiştirmez" listesinde olduğunu kontrol edin. Böylece yeni bir rota eklendiğinde test bunu hatırlatır.

**B-O7. Kayıt düzenleyicinin ve yedeklerin içeriği kontrol edilmiyor; bir beklenen değer döngüsel.** [Ö: mutantlar; güven yüksek]
- 26 save_engine ve 27 sunucu mutantı sağ kaldı. Kontrol edilmeyenler:
  - yedeklenen anahtarlar (`BACKUP_KEYS`), `list_backups`'ın döndürdüğü alanlar ve zaman damgaları;
  - düzenleyici sayfasının gösterdiği JSON;
  - düzenleyicinin yazdığı battle/fleets/population, `saved` işareti ve yedek mesajı.
- Form anahtarı `restore<n>` ile yedekten geri dönüş (`empires-server.py:556`) kayıt testlerinde hiç kullanılmıyor.
- `empires_test.py:414-420` beklenen yedek sayısını `backup_db.MAX_BACKUPS`'tan alıyor. Bu yüzden `MAX_BACKUPS = 21` değişikliği fark edilmiyor.
- *Düzeltme:*
  - Bir kaydı yedekleyip geri yükleyin. `BACKUP_KEYS`'teki her anahtarın aynı değerle geri geldiğini kontrol edin; anahtar listesini testte elle yazın.
  - `list_backups`'ın `saved_on`/`replaced_on` değerlerini, `monkeypatch` ile sabitlenmiş saatle karşılaştırın.
  - Yedek sayısı için sabit `20` yazın ve gerekçesini yorumda belirtin.
  - `/save-editor`'e `restore0` gönderen bir test ekleyin; geri dönen kaydın yedekteki kayıt olduğunu kontrol etsin.

**B-O8. Hata yollarının kurulumu test edilmiyor: 500 işleyicisinin kaydı, `transactional_session` ve Ruffle yolu.** [Ö: mutantlar #301, #351, #352, #299; güven yüksek]
- `@app.errorhandler(500)` → `501` değişikliği fark edilmedi. Sebep: testler `server_error_page()`'i doğrudan çağırıyor (`session_layer_test.py:527`).
- `@transactional_session`'ın tamamen kaldırılması da fark edilmedi. `guarded_call` dışında patlayan bir istek (örneğin bozuk bir AMF gövdesi) hiç gönderilmiyor.
- Ruffle'ın kullandığı `/127.0.0.1flashservices/gateway.php` yolu da hiç çağrılmıyor.
- *Düzeltme:*
  - Test istemcisiyle bozuk bir AMF gövdesi gönderin (editörü monkeypatch'leyerek).
  - Yanıtın 500 ve `'It went wrong'` olduğunu, veritabanındaki kaydın istekten önceki haliyle bayt bayt aynı kaldığını kontrol edin.
  - Aynı `batch()` testini iki ağ geçidi yolu için parametreleyin.

### Düşük

**B-D1. Testler depo klasörüne yazıyor.** [Ö, güven yüksek]
- Her koşuda `log.txt` yazılıyor: `save_engine.py:199` `os.path.join(log_path(), "log.txt")`, `log_path()` = `.`.
- İlk koşuda `cache/directory.cache` ve `cache/mods.config.cache` oluşuyor.
- `empires-server` import edilirken `save_database_uri` çağrılıyor; kökte bir `save.db` varsa onu `instance/`'a taşıyabilir [Ç].
- *Düzeltme:* `conftest.py`'de `log_path` ve önbellek klasörü `tmp_path_factory`'ye yönlendirilmeli. Bir oturum sonu kontrolü depo ağacının değişmediğini doğrulamalı (`denetim2_leaks.py` buna örnek).

**B-D2. Zamana dayalı bekleme.** [Ç, güven orta]
- `session_layer_test.py:131` `assert not fast_done.wait(0.5)`. Çok yavaş bir makinede kilit olmasa bile hızlı istek 0,5 saniyeyi aşabilir ve test yanlışlıkla geçer (yanlış alarm değil, kaçırma).
- Sonrasındaki depolanmış filo kontrolü deterministik, bu da riski azaltıyor.
- Diğer örnekler: `join(10)` (satır 134, 136, 530) ve `bounty_center_test.py:28` `time.time() - 1`.
- *Düzeltme:* Kilit `threading.Event` ile "yavaş istek kilidi tutarken" noktasında durdurulmalı. Hızlı isteğin o anda beklediği `lock.locked()` ya da sayaçla kontrol edilmeli.

**B-D3. İstemci modelinde eksik kurallar.** [Ç, güven yüksek]
- Eksik kurallar: `damage - upgradeDamage == 0` → +1 ve "weaker" birlikleri.
- Şu anki havuzda etkisi yok. Ama B-Y2 genişletilince gerekecek.
- *Düzeltme:* Bayt koddaki `resolveAttack` dalı modele eklenmeli. Havuza bir "weaker" birlik konmalı.

**B-D4. Gizli tutarsızlık: çevresel (collateral) hasar hâlâ eski `against` kuralını kullanıyor.** [Ç, güven yüksek]
- `battle_engine.py:1114-1116`:
  ```
  for a in against:
      if a['-type'] in (get_unit_type(…), get_unit_terrain(…)):
          colateral_damage *= …
  ```
  Burada `break` yok ve birliğin bütün türlerine bakılmıyor.
- Hedef birlikteki satır 1075-1078 ise istemcinin ilk-eşleşme kuralına çevrilmiş.
- Bugün hiçbir birliğin 3. veya sonraki türü "aircraft" olmadığı için etkisi yok. Bunu bir test de kontrol etmiyor.
- *Düzeltme:* İki döngü tek bir `get_modifier(unit, against)` yardımcısına toplanmalı. Testte yapay bir birlikle (türler `["x","y","aircraft"]`) iki `against` eşleşmesinde yalnızca ilkinin uygulandığı kontrol edilmeli.

**B-D5. Zayıf testler (9 W).** [Ç, güven yüksek]

| Test | Sorun |
|---|---|
| `bot_empires_test.py:64-65` `assert 1.03 < bot_empires.STRENGTH_PER_LEVEL < 1.06` | sabitin aralık kontrolü |
| `empires_test.py:391-392` `SESSION_COOKIE_SAMESITE == 'Strict'` | ayarın geri okunması; çerezin yanıtta `SameSite=Strict` olduğu kontrol edilmeli |
| `empires_test.py:513` `test_click_on_dormant_tree_is_ignored` | setState hiçbir şey yapmasa da geçer |
| `quest_trees_test.py` `== hook_spots(...)` | — |
| `session_layer_test.py` "her durum makinesi aranabilir" | yalnızca exception olmamasına bakıyor |

- *Düzeltme:* Her biri için gözlenebilir bir çıktı kontrol edilmeli. Örnek: çerez başlığı; kuru ağaca tıklayınca kaynakların ve `lastEnergyCheck`'in aynı kaldığı.

**B-D6. Döngüsel beklenen değerler (10 C).** [Ç, güven orta-yüksek]
- `megaseries_test.py` ve `quest_trees_test.py` beklentiyi modülün kendi okuduğu veriden (`megaseries.nodes`, `quest_trees.first_quest`, `hook_spots`) alıyor.
- `bot_empires_test.py` denge testi, motordan yazılmış kendi modelini kullanıyor.
- `titan_lab_test.py` beklenen zarı `battle_engine.get_hit_value` ile hesaplıyor.
- *Düzeltme:* Bu beklentiler `client_settings.py` gibi testin kendi XML okuyucusundan gelmeli.

**B-D7. Kayıt göçünün yarısı denetimsiz.** [Ö, güven yüksek]
- Göç mutantlarının yalnızca %48,3'ü öldürüldü.
- 0.08a adımının koyduğu 12 deney değeri (`save_migration.py:66-77`) kontrol edilmiyor.
- 0.04a'dan başlayan bir kayıt hiç denenmiyor.
- B-O4 ile birlikte düzeltilmeli. Her adımın beklenen değerleri göç kodundan alınmamalı; o sürümün değişiklik notundan ya da istemcideki deney adlarından elle yazılmalı.

**B-D8. Eski bir editör izi.** [Ö, güven yüksek]
- Depo kökünde 2026-10-31 13:22 tarihli `.log.txt.swp` var (Vim 9.2 takas dosyası).
- Dosya bu denetimden önce, bir çökmenin ardından `log.txt`'nin editörde açıldığını gösteriyor. Görevde uyarılan riskle tutarlı.
- Dosya silinmedi; depoya dokunulmadı.

### Olumlu bulgular [Ö + Ç, güven yüksek]

- `battle_turn_test.py`'deki istemci modeli bayt koduna uyuyor (§4) ve savaş çekirdeğinin mutantlarının çoğunu öldürüyor (§5).
- `session_layer_test.py` gerçek AMF ağ geçidinden geçiyor: kodlama, oturum katmanı, kilit, geri alma ve kayıt doğrulama birlikte sınanıyor.
- Hiç atlanan test, tolerans veya yutulan exception yok. Ağ kullanımı ve sızan iş parçacığı yok.
- `client_settings.py` XML'i bağımsız okuyor ve sözlük sırasının sonucu belirleyemediğini kendisi kontrol ediyor.

---

## 7. Boşluklar (özet)

- **Hata yolları:**
  - Ağ geçidinde başarısız çağrının geri alınması test ediliyor.
  - İşleyicilerin kendi hata yolları test edilmiyor: yetersiz para, olmayan eşya kodu, bayat filo adı (`StaleBattleReference` yalnızca birkaç yerde).
- **Sınır değerleri:**
  - Ödül sınırı (a = 100, battle_engine.py:245) ve 1 hasar sınırı (:124) test edilmiyor; ikisinin mutantı da sağ kaldı.
  - Yedek sayısı sınırı yalnızca döngüsel olarak kontrol ediliyor (B-O7).
  - Buna karşılık AI oran sınırının (tam 0,5) `<` → `<=` değişikliği yakalandı (hedefli mutant B8, §5.2).
- **HTTP/AMF ve doğrudan çağrı:**
  - session_layer_test (36 test) uçtan uca.
  - Geri kalan testlerin büyük kısmı `app.test_request_context()` içinde fonksiyonları doğrudan çağırıyor.
  - Savaş akışının tamamı (`battle_complete_response`) hiç AMF üzerinden sınanmıyor.

---

## 8. Hüküm: "Testler sırf geçsin diye mi yazılmış?"

**Hayır.** [Ç, güven yüksek; dayanakları Ö]

- 227 testin %67'sinin beklenen değeri bağımsız bir kaynaktan geliyor: istemci modeli, XML ya da girdiden türetme. Gerçekten "kendini kontrol eden" (C+W) test oranı %8.
- Savaş çekirdeğinde hedefli mutantların 10/10'u, rastgele mutantların %79'u (eşdeğerler hariç 141/178) öldürüldü. "Sırf geçsin" diye yazılmış bir test takımında bu oranlar çok daha düşük olurdu.
- Kayıt ve oturum katmanında hedefli mutantların 15/15'i öldürüldü. Eşzamanlılık testi, kilidin temiz biçimde kaldırıldığı S1b'yi doğru testle yakaladı.
- Rastgele mutantlarda genel skor %69,7 (370/531).

**Ama testler dar.**
- Sunucu dosyasındaki dalların dörtte üçü hiç çalışmıyor.
- Savaş testleri tek bir yapılandırmada kalıyor.
- Beklenen değerlerin dörtte biri (M+S, %25) türetmesiz.

Bu yüzden "geçen testler = doğru oyun" ancak denenmiş bölgeler için söylenebilir. Bütün sunucu için söylenemez.

**Not: 6/10.**

| Etken | Puana etkisi |
|---|---|
| Beklenen değer kalitesi | +2,5 |
| Savaş çekirdeğinin hata yakalama gücü | +1,5 |
| Kayıt ve oturum katmanının hata yakalama gücü | +1 |
| Güvenilirlik | +0,5 |
| Kapsam | +1 (dalların %47,8'i; sunucuda %25,5) |
| Anlık görüntü ve sabit sayı payı, sıra bağımlılığı, zayıf testler | −0,5 |

---

## 9. Ölçülen / çıkarılan ayrımı

| İddia | Tür | Güven |
|---|---|---|
| Kapsam, güvenilirlik ve mutasyon sayıları | Ö | yüksek (komutlar §2) |
| Mutasyon skorunun bütün dosyaya genellenmesi | Ç (örneklem + Wilson güven aralığı) | orta |
| Eşdeğer mutant kararları | Ç (her biri için gerekçe yazıldı) | yüksek |
| Oracle sınıflandırması | Ç (denetçi yargısı, `oracle_siniflandirma.py`'de gerekçeleriyle) | orta-yüksek |
| İstemci modelinin bayt koduna uyması | Ç (söküm okuma) | yüksek |

---

## 10. Betikler (`scratchpad\denetim2\`)

| Betik | Ne yapıyor |
|---|---|
| `run_pytest_denetim2.py` | pytest başlatıcısı. Tekil `argv[0]` verdiği için tek-örnek kilidi diğer işle çakışmıyor. |
| `cov_summary.py` | coverage.json'dan dosya başına satır ve dal oranı. |
| `plugins\denetim2_shuffle.py` | `SHUFFLE_SEED` ile karışık veya ters sıralama. |
| `plugins\denetim2_leaks.py` | Depoya yazılan dosyalar, canlı kalan iş parçacıkları, ağ çağrıları. |
| `reliability.ps1` | 3 normal + 1 ters + 5 karışık + dosya başına tek koşu. |
| `mut_harness.py`, `mutation_runs.ps1`, `mut_summary.py` | Mutasyon koşturucusu (yeniden başlatılabilir) ve özet. Sonuçlar: `mut_*.json`, `mut_*.log`. |
| `mut_recheck.py` | Sağ kalanları bütün test takımıyla yeniden koşturur ve `full_status` alanını yazar (`mut_recheck.log`). |
| `mut_survivors.py` | Sağ kalanların E/G sınıflaması ve gerekçeleri; eşdeğerler hariç skor ve Wilson aralığı. `--list` seçeneği `mut_survivors.txt`'yi üretir. |
| `after_mutation.sh` | Mutasyon koşusu bittikten sonra hedefli mutantları ve yeniden denemeyi sırayla çalıştırır. |
| `targeted_mutants.py` | 25 hedefli mutant (S1b dahil). Sonuç: `targeted_mutants.json` ve `.log`. |
| `oracle_siniflandirma.py` | Beklenen değer sınıflandırması ve sayım. |
| `vault_flake_odds.py` | Kasa testinin şans eseri başarısız olma ihtimali. |
| `abc_signature.py`, `bytecode\*.txt` | Bayt kodu imzaları ve dökümleri. |

---

## 11. Bağımsızlık ve depo notu

Yasak kaynaklar okunmadı. Ancak iki kazara maruz kalma oldu; ikisi de kullanılmadı ve bulguları etkilemedi:

1. Depo genelindeki bir `grep` çıktısı `docs\denetim\hesap\…` altındaki dosyalardan birkaç satır gösterdi.
2. `git worktree add` komutunun çıktısında HEAD commit'inin başlığı göründü.

Depo değiştirilmedi:
- Bütün mutasyon deneyleri `denetim2\wt` worktree'sinde yapıldı; worktree sonunda `git worktree remove --force` ile kaldırıldı.
- Depo kökünde yapılan temel ve kapsam koşuları, testlerin kendisi yüzünden git'in yok saydığı `log.txt`'ye yazdı (B-D1).
- `git status` başlangıçtakiyle aynı: 7 değişmiş dosya, `test/client_settings.py` ve önceden var olan `.log.txt.swp`.
