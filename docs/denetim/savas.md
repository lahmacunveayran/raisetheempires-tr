# Savaş ve PvP — Bağımsız denetim raporu
Denetçi: bağımsız denetçi (Savaş ve PvP). Kaynak: denetim-1 @ a4de86e. Tarih: 31 Ekim 2026.

## Özet

**Puan: 5/10.**

Savaşın temeli sağlam: sunucunun rastgele sayı üreticisi istemcininkiyle bit bit aynı; sıradan birimlerde hasar
formülü, isabet tablosu ve düşmanın hangi birimle kime vuracağını seçen yapay zekâ istemcideki kodun neredeyse birebir
kopyası (istemcinin kendi küçük hatası bile bilerek taklit edilmiş). Bot rakiplerin denge iddiaları da yeniden
hesaplayınca büyük ölçüde doğru çıktı. Ama istemci her savaş hamlesinden sonra sunucunun cevabını kendi hesabıyla
karşılaştırıyor ve seçilen birimler ya da zar tohumu tutmazsa işlemi **hata ile kesiyor**
(`TResolveBattle.onComplete` → `error` → `TransactionFaultEvent`). Sunucunun istemciden ayrıldığı her yer bu yüzden
doğrudan oyunu bozuyor. En önemlileri:

1. **Titan savaşlarında sunucu yanlış güçle hesaplıyor (SAV-01).** Titan birimlerinin bir "dayanıklılık" bir de
   "saldırı" gücü var; sunucu saldırı gücünü hiç okumuyor. Sunucuya göre oyuncu Titan'a 8 kat, Titan oyuncuya
   yaklaşık 2 kat fazla vuruyor; Titan Laboratuvarı parça savaşları istemcinin gösterdiğinden bambaşka ilerliyor.
2. **Oyuncunun kalan birimleri sersemletilince sunucu çöküyor (SAV-02).** Düşman destek birimlerinin "sersemletme"
   gücü oyuncunun son hayatta kalan birimine gelirse, düşmanın sıradaki hamlesinde sunucu hata veriyor; savaş donuyor.
3. **Yuvarlama farkı her 67 savaştan birini kesiyor (SAV-03).** Eşit adaylar arasında seçim yaparken sunucu Python'un
   yuvarlamasını (yarımı çifte), istemci yarımı yukarı yuvarlıyor. 3000 savaşlık denemede savaşların %1,5'inde düşmanın
   seçtiği birim istemcininkinden ayrıldı; istemci bu durumda işlemi hata ile kesiyor.
4. **Güç (consumable) ile öldürmenin ödülü ters tarafa yazılıyor (SAV-04).** Oyuncu hava saldırısı gibi bir güçle
   düşman öldürünce para/XP/"öldür" görevi ilerlemesi almıyor; düşmanın gücü oyuncunun kendi birimini öldürünce alıyor.
5. **Testler savaşın kendisini ölçmüyor (SAV-08).** Savaş testleri yalnız savaşın kuruluşuna bakıyor; hasar, yapay
   zekâ seçimi, tohum uyumu, ödül, kazanma/kaybetme için tek test yok. Yukarıdaki hataların hiçbiri test kırmıyor.

Bulgu sayısı: **Kritik 0, Yüksek 4, Orta 4, Düşük 4.**

Yardımcı betikler `docs/denetim/hesap/savas/` altında; hepsi depo kökünden
`../venv312/Scripts/python.exe docs/denetim/hesap/savas/<betik>.py` ile çalışır ve depoda hiçbir şeyi değiştirmez.

## Bulgular

### SAV-01 — Titan birimlerinde sunucu "saldırı gücü" yerine "dayanıklılığı" kullanıyor
- **Önem:** Yüksek. **Güven:** kesin (kod ve çalıştırma), oyundaki sonucu yüksek.
- **Yer:** `battle_engine.py:1242-1247` (`get_unit_max_strength`), kullanıldığı yer `battle_engine.py:69-73`.
- **Kanıt:** Titan (ML..) birimlerinde güç seviyeye göre `<strengths><entry strength=.. attackStrength=..>` ile
  verilir. Sunucu yalnız `strength`'i okur:
  `strength = int(next((e for e in entries if level < int(e["-level"])), entries[-1])["-strength"])`.
  İstemcide `BattleAI.GetAttackingDamage` saldıranın gücünü `GetAttackingStrengthAgainst(..., STRENGTH_MAX)` =
  `unitItem.getAttackStrength(fleet)` ile, hasar çarpanını da savunanın `getAttackStrength`'iyle alır;
  `UnitItem.getAttackStrength` → `getXmlStrength(fleet, true)` → Titan için `entry.attackStrength` döndürür
  (sıradan birimlerde `strength` özniteliği olduğu için ikisi aynıdır, fark yalnız Titanlarda). Çalıştırma:
  ```
  > python docs/denetim/hesap/savas/titan_hasar.py
  Titan ML11 seviye 25 : strength 2400 attackStrength 300 | sunucunun kullandigi en yuksek guc: 2400
  oyuncu -> Titan duz vurus hasari: sunucu 232.653 istemci 29.081 oran 8.0
  Titan -> oyuncu duz vurus hasari: sunucu 96.71 istemci 52.5 oran 1.84
  Titan'i oldurmek icin oyuncu vurusu: sunucu (asil motor, karisik isabetler) 24 | istemci (hep duz vurus) 67
  ```
- **Oyuncuya etkisi:** Titan Laboratuvarı parçası için savaşan oyuncu ekranda Titan'ı yavaş yavaş eritirken sunucu
  onu çoktan öldürmüş sayar: ödülü (3 parça) verir, `session["mechlab"]`'ı ve savaş durumunu sıfırlar; sonraki
  hamlede sunucu aynı filoyla tam güçte yeni bir savaş başlatır. İki taraf artık farklı birimleri hayatta saydığından
  düşmanın seçtiği birimler tutmaz ve istemci işlemi hata ile keser; ya da sunucu oyuncunun birimlerini 2 kat hızlı
  öldürüp savaşı kaybedilmiş sayar (Titan filosu silinir, sonraki istek `StaleBattleReference`'a düşer). Oyuncunun kendi
  Titan'ı ile yaptığı her savaş da aynı yanlışla hesaplanır. `test/titan_lab_test.py:89-95` dayanıklılığı (2400/6000)
  doğruluyor ama saldırıda bu sayının kullanılmasını yakalamıyor.
- **Öneri:** Birim için iki ayrı değer üretin: `get_unit_max_strength` (dayanıklılık, `strength`) ve
  `get_unit_attack_strength` (`attackStrength`, yoksa `strength`). Hasar formülünde istemci gibi
  `A = saldıranın saldırı gücü`, `D = savunanın o anki gücü`, çarpan `= savunanın saldırı gücü` kullanın. İstemci
  seviyeyi filonun `playerLevel`'ından okur; sunucu oyuncunun seviyesini kullanıyor, bunu da eşitleyin.

### SAV-02 — Oyuncunun hayatta kalan bütün birimleri sersemlemişken düşman hamlesi sunucuyu çökertiyor
- **Önem:** Yüksek. **Güven:** kesin.
- **Yer:** `battle_engine.py:1192-1198` (`ai_best_attack`, 2. yöntem).
- **Kanıt:** `ai_best_unit(..., "ally")` sersemlemiş birimleri atlar; hepsi sersemse her düşman için `(None, -1)`
  döner. `best_players = [None, ...]` boş olmadığı için `player_units[best_player]` = `player_units[None]` çalışır.
  İstemcide aynı yer (`BattleAI.FindBestDefendingUnitAgainstBestAttacker`) yalnız değer `> -1` olunca saldıran seçer,
  yoksa ikinci zarı atmaz ve hata vermez. Çalıştırma:
  ```
  > python docs/denetim/hesap/savas/kazalar.py
  == 1. Butun oyuncu birimleri sersemlemisken AI turu
  COKTU: TypeError list indices must be integers or slices, not NoneType
    File ".../battle_engine.py", line 1198, in ai_best_attack
  ```
  Sersemletme gücü N64 (`-disable: stun`, `-castpercent: 0.2`) US14, US20, SU06 destek birimlerinde var; bunlar oyun
  verisindeki düşman filolarında 52 kez geçiyor (yalnız `"-SU06": "1"` 28 kez).
- **Oyuncuya etkisi:** Tek birimi kalmış oyuncunun birimi sersemletilir; düşmanın sıradaki hamlesi (istemci bu
  durumda %80 olasılıkla hamleyi yine gönderir) sunucuda 500 hatası verir. `transactional_session` kaydı geri alır ama
  istemci "net status failure" ile kalır; savaş sürdürülemez.
- **Öneri:** `if best_players and best_players[0] is not None:` (ya da `max_grade_2 >= 0`) koşulu; değilse ikinci zarı
  atmadan `(None, 0, None)`. Bu durum için bir test ekleyin.

### SAV-03 — Eşitlik bozmada Python `round()` istemcinin `Math.round`'undan farklı
- **Önem:** Yüksek. **Güven:** kesin (mekanizma ve sıklık ölçüldü).
- **Yer:** `battle_engine.py:1185`, `1223` (yapay zekâ), `914`, `954`, `971` (güç hedefi ve müttefik gücü seçimi).
- **Kanıt:** İstemci (`BattleAI.findBestUnit`, `FindBestDefendingUnitAgainstAttackers`,
  `ConsumableItem.getRandomConsumableForLevel`, `Fleet.getRandomUnitIndexFromList`) `int(Math.round(r*(n-1)))`
  kullanır; AS3 `Math.round` yarımı yukarı yuvarlar. Python 3 `round` yarımı çifte yuvarlar (`round(0.5) == 0`).
  ```
  > python docs/denetim/hesap/savas/yuvarlama.py
  aday sayisi 2 : farkli secim veren r degerleri 1 / 1000 -> [(0.5, 0, 1)]
  aday sayisi 3 : farkli secim veren r degerleri 1 / 1000 -> [(0.25, 0, 1)]
  aday sayisi 5 : farkli secim veren r degerleri 2 / 1000 -> [(0.125, 0, 1), (0.625, 2, 3)]
  > python docs/denetim/hesap/savas/yuvarlama_mac.py 3000
  mac: 3000 AI turu: 43935 AI seciminin istemciden ayrildigi mac: 45 (1.50%)
  ```
  (İkinci betik aynı savaşı aynı tohumla asıl motorda bir kez bugünkü `round`, bir kez AS3 yuvarlamasıyla oynatıp düşmanın
  seçtiği birim çiftini karşılaştırır.)
- **Oyuncuya etkisi:** Her ~67 savaştan birinde düşmanın seçtiği birim istemcininkinden farklı çıkar; istemci
  "unit IDs out of sync" ile işlemi hata olarak keser. Oyuncu bunu "arada bir savaş ortasında oyun takıldı" diye yaşar.
- **Öneri:** Tek bir `as3_round = lambda x: math.floor(x + 0.5)` yardımcısı yazıp bu beş yerde kullanın.

### SAV-04 — Güçle öldürmede ödül ve "battleKill" görev ilerlemesi ters tarafa yazılıyor
- **Önem:** Yüksek. **Güven:** kesin (kod ve çalıştırma).
- **Yer:** `battle_engine.py:1067-1073` ve `1098-1104` (`apply_consumable_direct_impact`).
- **Kanıt:** `ally` parametresi hedef birimlerin oyuncunun olduğunu gösterir (`friendlies` ile çağrılırken `True`).
  Öldürülen birim için ödül `if ally:` altında verilir, yani yalnız oyuncunun **kendi** birimi ölünce:
  ```
  > python docs/denetim/hesap/savas/kazalar.py
  == 2. Guc ile oldurme odulu
  oyuncu dusmani oldurdu: dusman gucleri [0, 100] | para 5000 -> 5000 | xp 0 -> 0
  dusman oyuncunun birimini oldurdu: oyuncu gucu [0] | para 5000 -> 5009 | xp 0 -> 1
  ```
  Aynı blok `progress_battle_damage_count("battleKill", 1, {}, units[targeted_unit])` ile ölen **kendi** birimini
  "öldürülen düşman" olarak göreve sayar. Ayrıca güç hasarı hiçbir zaman `battleDamage` görevine ve vuruş başı paraya
  yazılmaz; istemci ise güç isabetlerinde de `BattleUnit.onUnitHit` → `EnemyUnit.playDamageXPReward` ile ödül gösterir.
- **Oyuncuya etkisi:** "Hava saldırısıyla 5 tank yok et" gibi görevler güçle yapılan öldürmeleri saymaz; düşman
  topçusu oyuncunun tankını güçle öldürünce "tank öldür" görevi ilerler ve oyuncu para/XP kazanır. Ekranda görülen
  güç ödülleri yeniden yüklemede kaybolur.
- **Öneri:** Koşulu `if not ally:` yapın, `doBattleRewards`'a gerçek hasarı ve saldıranın gücünü verin; güç hasarı
  için `battleDamage` ilerlemesini de ekleyin. Oyuncunun birimi ölünce istemcinin verdiği "kayıp" ganimetini
  (`PlayerUnit.playDamageXPReward`: para, petrol, 1 nadir kaynak) ayrıca ele alın (SAV-06).

### SAV-05 — Araştırma güç yükseltmesinde sunucu yuvarlamıyor, istemci yuvarlıyor
- **Önem:** Orta. **Güven:** kesin (mekanizma), sıklık ölçüldü.
- **Yer:** `battle_engine.py:344-357` (`handle_strength_upgrades`; `bot_empires._unit_strength` de bunu kullanır).
- **Kanıt:** Sunucu `strength *= 1 + float(mod) / 100`; istemci `WorldUpgradeManager.getModifiedStrength`
  `s = Math.round(s + s*mod/100)`. Oyuncu birimleri sunucuda ondalıklı güçle başlar (testteki `[180.0, 180.0, ...]`
  de bunun izi):
  ```
  > python docs/denetim/hesap/savas/arastirma_gucu.py
  XS02 +50% : farkli 6 / 20      XS03 +33% : farkli 28 / 34      XS04 +25% : farkli 50 / 98
  ornekler (birim, guc, yukseltme, sunucu, istemci): [('SK6', 90, 'XS04', 112.5, 113), ('AU06', 80, 'XS03', 106.4, 106), ...]
  > python docs/denetim/hesap/savas/arastirma_mac.py 1000
  mac: 1000 | AI secimi ya da sonucu istemciden ayrilan: 3 (0.3%) | kazanan taraf degisen: 1
  ```
  (Yükseltmeyi birimin kademesine göre `XS0<kademe>` diye eşledim; eşleme benim varsayımım.)
- **Oyuncuya etkisi:** Kademe 2-4 birimlerini araştırmayla güçlendiren oyuncuda yaklaşık 300 savaşta bir, sunucu ile
  istemci farklı birimi ölü sayar: ya istemci hata ile keser ya da sunucu savaşı farklı bitirir (ödül verilmez ya da
  yanlış verilir). Titan güç yükseltmeleri (TS01-08, +%25) de aynı yoldan geçer.
- **Öneri:** Her yükseltmeden sonra `math.floor(s + s*mod/100 + 0.5)`; yüzde olmayan yükseltmede de aynı yuvarlama.

### SAV-06 — Vuruş ödülleri ve ödül zarı istemciden ayrı hesaplanıyor
- **Önem:** Orta. **Güven:** yüksek (istemci kodu okundu; oyundaki etkinin boyutu olası).
- **Yer:** `battle_engine.py:1335-1390` (`doBattleRewards`), `battle_engine.py:92-116`.
- **Kanıt:** İstemci `EnemyUnit.playDamageXPReward` her hasarlı vuruşta `ZGameRandom.rewardInstance.float()` atar
  (doober tablosu, bytecode 698); sunucu ödül zarını yalnız kritik vuruşta atar (`1353-1358`). Böylece ödül tohumu
  (`rewardRandSeedW/Z`) ilk sıradan vuruşta istemciden ayrılır; bu tohumu kullanan öteki "zorunlu" atışlar da
  (`state_machine.py:128-130`) artık istemciyle aynı sonucu vermez. Ayrıca: nadir kaynağın türü istemcide saldıranın
  **o anki** gücünden (`BattleUnit.onUnitHit` → `attackerStrength = attacker.unit.strength`, `getRareType` →
  `"nrare" + güç % 5`), sunucuda en yüksek gücünden (`1345`) seçilir; sıyırma (glancing) ile öldürmede istemci para
  vermez, sunucu `"kill"` sayıp para verir (`112`, `1347`); oyuncunun birimi düşman vuruşuyla ölünce istemcinin
  gösterdiği para/petrol/nadir ganimet sunucuda hiç verilmez (`# TODO combat losses`, `1343`).
- **Oyuncuya etkisi:** Savaştan sonra ekranda toplanan enerji, nadir kaynak türü ve para miktarı yeniden yüklemede
  farklı çıkar (küçük ama sürekli sapma).
- **Öneri:** İstemcinin ödül sırasını izleyin: her hasarlı vuruşta ödül zarını istemcinin attığı kadar atın, nadir
  türünü saldıranın o anki gücünden alın, sıyırmada para vermeyin, birim kaybı ganimetini ekleyin.

### SAV-07 — "Eski istek" cevabı istemciyi yine hataya düşürüyor
- **Önem:** Orta. **Güven:** olası.
- **Yer:** `empires-server.py:911-916`, `3028-3031`.
- **Kanıt:** `StaleBattleReference` yakalanınca `dummy_response()` (`"data": []`) dönülüyor. `resolveBattle`
  cevabını istemci `TResolveBattle.onComplete` ile okur: `[].playerUnit` tanımsızdır, `m_playerID` ile eşleşmez ve
  `error(...)` → `TransactionFaultEvent(INVALID_DATA)` olur. Yani 500 yerine yine bir hata; yalnız sunucu tarafı
  temiz kalır. (Bu cevabın istemcide tam olarak ne gösterdiğini oyunda deneyemedim.)
- **Oyuncuya etkisi:** SAV-01'deki gibi sunucunun savaşı önce bitirdiği durumlarda istemci yine takılır.
- **Öneri:** Eski isteğe istemcinin beklediği alanlarla (`playerUnit`, `enemyUnit`, `seeds`, `ps`, `es`, `ur`) bir
  cevap verin; en azından istekteki `id` ve o anki tohumlarla.

### SAV-08 — Savaş testleri savaşın kendisini ölçmüyor
- **Önem:** Orta. **Güven:** kesin.
- **Yer:** `test/battle_test.py` (tümü), `test/bot_empires_test.py:165-253`, `test/titan_lab_test.py:98-105`.
- **Kanıt:** `battle_test.py`'deki 29 testin hiçbiri `battle_complete_response`, `ai_best_attack`, `handle_win`,
  `handle_loss` ya da `doBattleRewards`'ı çağırmıyor; "ai" adlı testler (`test_init_battle_ai`, `..._ai_invade`) bile
  yalnız `init_battle`'ın döndürdüğü listeleri karşılaştırıyor. Tohum dizisi, hasar sayısı, düşman seçimi, ödül ve
  kazanma/kaybetme için tek beklenen değer yok; SAV-01..04 test kırmadan duruyor. Bot denge testi motoru değil
  kendi kopyasını (`battle()`) oynatıyor; kopya bugün motorla istatistik olarak aynı (aşağıda), ama motorda bir
  düzeltme (ör. SAV-01) yapılınca test bunu görmez. Titan zafer testi savaş oynamadan `handle_win([0]*5, ...)`'i
  doğrudan çağırıyor.
- **Öneri:** Bilinen tohumla birkaç tam savaş oynatan, her hamlede `ur`, `ps/es`, `playerUnit/enemyUnit` ve
  `seeds`'i istemciden alınmış (ya da istemci koduna göre elle hesaplanmış) değerlerle karşılaştıran testler; SAV-02
  ve SAV-04 için birer test; bot testinde kopya yerine `battle_complete_response`'u kullanın (betik
  `bot_denge.py:engine_battle` hazır bir örnek).

### SAV-09 — Uçaksavar NPC birimleri saldırırsa sunucu çöker
- **Önem:** Düşük. **Güven:** kesin (çökme), olası (oyunda bu filolarla karşılaşma).
- **Yer:** `battle_engine.py:584` (`[chain] = [...]`).
- **Kanıt:** `antiairland` (PU6, PU8) ve `antiairship` (PS4, PS8) türleri `combatChain`'de yok:
  `get_hit_value("antiairland", "tank")` → `ValueError: not enough values to unpack (expected 1, got 0)`. Bu birimler
  B72, B78, B79, B90, B92, B93 düşman filolarında var; bu filoları kullanan bir görev `questsettings`'te bulamadım.
- **Öneri:** Zincirde olmayan tür için "good" (ya da istemcinin `CombatChain`'inin verdiği değer) döndürün.

### SAV-10 — Düşmanın ikinci yeteneği hep ilk adayın oranıyla, ölü birim de sayılarak seçiliyor
- **Önem:** Düşük. **Güven:** olası.
- **Yer:** `battle_engine.py:918-934`.
- **Kanıt:** Aday listesi `strength > 0` denetlemiyor ve her `"AI"` isteğinde `secondaries[0]`'ın `-castpercent`'i
  kullanılıyor. İstemci (`BattleHost.state_UseSecondaryAbility`) yetenekli her birim için sırayla ayrı bir
  `TAssignConsumable("AI", ...)` gönderip o birimin kendi oranıyla zar atıyor. İki farklı destek birimi olan (ya da
  ilk destek birimi ölmüş) filoda sunucu "yetenek kullanıldı" kararını istemciden farklı verebilir. Kodun kendisi bunu
  `WARN: more that one secondary` diye yazıyor.
- **Öneri:** Hayattaki, sersemlememiş birimleri sırayla izleyin; her "AI" isteğinde sıradaki birimin oranını kullanın.

### SAV-11 — Bot dengesi belgede biraz iyimser; denge testi tek tohuma bağlı
- **Önem:** Düşük. **Güven:** kesin (ölçüm).
- **Yer:** `bot_empires.py:18-22` (docstring), `test/bot_empires_test.py:232-253`.
- **Kanıt:** Belgeye göre 54 rastgele takım 5 basamağa karşı ~%58, 54, 49, 39, 33 kazanıyor. Kendi 54 takımımla
  (her takım x bot 20 maç):
  ```
  > python docs/denetim/hesap/savas/bot_denge.py 6 20 2024
  STRENGTH_PER_LEVEL = 1.0411  HANDICAP faktoru = 0.904
  test benzetimi  (5 adim): [0.545, 0.489, 0.469, 0.407, 0.344]
  asil motor      (5 adim): [0.543, 0.496, 0.45, 0.399, 0.352]
  HANDICAP=0, esit seviye botu: oyuncu kazanma (benzetim / motor): 0.381 / 0.382  -> botun kazanma: 0.619 / 0.618
  ```
  Sıralama ve "tam ayna %63 kazanır" iddiası doğru; en kolay iki basamak belgedekinden 4-5 puan zor, "eşit maç"
  denen orta basamakta oyuncu %45-47 kazanıyor. Testteki 18 takımlık örnek tohuma göre çok oynuyor (13 tohumda
  basamak 0: %47-68, basamak 2: %42-60, basamak 4: %25-43; `bot_denge.py 1 2 2024 yayilim`); test sabit tohum 7 ile
  geçiyor, sınırlar (`0.45 <= rates[0]`) bazı tohumlarda aşılır. Oyuncunun hasar/isabet araştırmaları ve güçler
  benzetimde yok; bunlar botları daha da kolaylaştırır.
- **Öneri:** Belgedeki sayıları güncelleyin; testte daha çok takım ya da birkaç tohumun ortalamasını kullanın.

### SAV-12 — Küçük sağlamlık açıkları (bot durum dosyası, Titan parça açma)
- **Önem:** Düşük. **Güven:** kesin (kod).
- **Yer:** `bot_empires.py:144-146`, `bot_empires.py:136-141`, `titan_lab.py:67`, `battle_engine.py:297`.
- **Kanıt:** `_write_state` dosyayı yerinde yazıyor; yazma yarıda kalırsa `_read_state` bozuk JSON'u sessizce `{}`
  sayar ve bütün bot işgalleri kaybolur. Durum dosyası yoksa ya da silindiyse savaşı kazanmak
  `invasion_complete`'te `KeyError` (`["u" + zid]`) verir; istek geri alınır ama bot dosyası yazılmışsa geri alınmaz
  (oturum dışı yan etki). `unlock_part` nakit yetip yetmediğine bakmadan düşüyor (eksi bakiye olabilir; istemci de
  denetliyor).
- **Öneri:** Geçici dosyaya yazıp `os.replace`; `invasion_complete`'te eksik kaydı atlayan `.get`; nakit denetimi.

## Sağlam bulunanlar

- **Rastgele sayı üreticisi:** `quest_engine.roll_random` istemcinin `ZGameRandom.random`'u ile aynı (36969/18000
  çarpanları, `uint` dönüş tipi — `abc_imza.py` ile doğrulandı: `ZGameRandom.random() : uint`), `float` istemci gibi
  `uint.MAX_VALUE`'ya bölüp 3 basamağa keser (`MathUtils.roundTo`, `ACCURACY = 3`), `randBetween` aynı.
- **Sıradan birimlerde hasar:** `25 * (3A + D) / (3D + A) / 100 * savunanın gücü`, güç değiştiricisi `max(…, 0)`,
  sonra araştırma hasarı, 3 basamağa kesme, sıyırma x0,10, kritik x1,5, yukarı yuvarlama ve düşmanı 1 güçte bırakmama
  kuralı istemcinin `GetAttackingDamage` / `resolveAttack`'iyle aynı sırada. `combatDamageBase` deneyi
  (`empire_combat_damage`) açık olmadığı için 25 sabiti doğru; `combatAICanMiss=false` iken düşmanın da sıyırması doğru.
- **İsabet zarı:** zayıf birimde -2/+2, değilse tek `randBetween(0,1)`; kritik için `roll != 2` koşulu istemcinin
  `STRONG_ROLL` denetimiyle aynı. Araştırma isabeti istemci gibi kritik ve doğrudan eşiklerinden düşülüyor.
- **Düşman yapay zekâsı:** `ai_best_attack` istemcinin `FindBestDefendingUnit` akışını (aynı ilk zarın iki yöntemde
  kullanılması, yalnız birden çok aday varken atılan zar, ilk saldıranın düşmanını koruyan "bugged pairing",
  `switchRatio 0.5`, `switchPercent 0.2`) doğru izliyor; odak ateşi deneyi kapalı olduğundan atlanması doğru.
  Yuvarlama (SAV-03) ve sersemletme (SAV-02) dışında fark bulamadım; asıl motor ile testteki kopya 54 takımda aynı
  oranları verdi.
- **Bot rakipler:** `STRENGTH_PER_LEVEL` = 1,0411 (belgedeki "yaklaşık %4"), HANDICAP 2,5 seviye = x0,904; tür
  eşleme (bombardıman uçağı → tank) zincire göre doğru; `SPREAD` yorumu ("0,5 ile 60'ta bir, 0 ile 8'de bir 1,5
  kattan fazla sapma") ölçümle yakın: 1/87 ve 1/9 (`spread.py`). Bot seviyeleri `GlobalPVPPlayerDelta*` ile, liste
  15 kişi (`GlobalPVPMaxInvasionSlots`), günlük sayaç `GlobalPVPFightListDuration` ile uyumlu.
- **İstek bazında geri alma:** `transactional_session` (`empires-server.py:823-842`) çöken bir istekte oyuncu
  kaydını isteğin öncesine döndürüyor; çökme kayıt bozmuyor (dış dosyalar hariç, SAV-12).
- **Ödül Merkezi ve Titan Lab parçaları:** enerji basamakları, etkin süre, 10 seviye sınırı, parça sayısı deneyleri
  ve parça açma zinciri kodla ve testlerle tutarlı; bu bölümlerde hata bulmadım.
- İlgili 56 test geçiyor (`pytest test/battle_test.py test/bot_empires_test.py test/bounty_center_test.py
  test/titan_lab_test.py`).

## Bakılamayanlar ve sınırlar

- Oyunu çalıştırıp istemcide denemedim; istemcinin davranışını yalnız bytecode'dan (`abc.py`, kendi
  `abc_imza.py`'m) okudum. `TransactionFaultEvent`'in ekranda tam olarak ne gösterdiğini görmedim.
- Güç (consumable) akışının zar sayısını (`Fleet.triggerConsumable` ana zarı kullanıyor), süreli hasar (DOT) ve
  kalkan sırasını istemciyle satır satır karşılaştırmadım; burada da ayrılık olabilir.
- Hayatta kalma (survival) modu, kampanya ustalık ödül çarpanları, `CommandoManager` hasar bonusu (istemcide var,
  sunucuda yok; ne zaman etkin olduğuna bakmadım) ve müttefik/paralı asker gücü seçimindeki süzgeç ayrıntıca
  denetlenmedi.
- Araştırma yükseltmesinin hangi birime uygulandığını (kademe eşlemesi) varsaydım (SAV-05).
- Oyuncunun gerçek kurulumuna ve kayıtlarına dokunmadım; tüm ölçümler test kullanıcısıyla (`test/init_user.json`) ve
  geçici bot durum dosyasıyla yapıldı.
