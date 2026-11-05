# Savaş ve PvP — Düzeltmelerin bağımsız yeniden denetimi
Denetçi: bağımsız denetçi (savaş yeniden denetimi). Kaynak: `denetim-1`, temel `61ac7a8` ile çalışma ağacı farkı.
Tarih: 5 Kasım 2026.

## Özet

**Puan: 8/10.**

Düzeltmelerin çoğu gerçekten işe yarıyor; istemcinin kodunu tek tek okuyup karşılaştırdım:

- Titan hasarı artık istemciyle aynı: 39 Titan birimi, 5 seviye, iki yön = 390 vuruşun hepsi tuttu.
- Bütün birimler sersemletilmişken sunucu artık çökmüyor.
- Eşit adaylar arasında seçim artık istemci gibi yuvarlanıyor: 82 birimlik havuzla 400 savaşta (7334 hamle) tek bir
  ayrılık bile çıkmadı.
- Araştırma gücü yuvarlanıyor; uçaksavar NPC'leri çökertmiyor; bot dosyası güvenli yazılıyor.
- Düşmanın ikinci yeteneği (destek birimi gücü) istemcinin sırasıyla seçiliyor. "AI tried" işaretleri doğru anda
  siliniyor: düşmanın saldırısında, atlanan turda ve düşman gücünün hedefli isteğinde.

**Bir yeni sorun var:** bir güç (hava saldırısı gibi) düşman birimini öldürmeden vurunca sunucu oyuncuya para ve XP
veriyor, ödül zarını da bir kez atıyor (YS-01). İstemci bunu yalnız birim ölünce yapıyor. Asıl denetimin SAV-04/06
iddiası bu noktada yanlıştı, düzeltme de bu yanlışı izledi. Oyuncu bir şey kaybetmiyor, oyun da çökmüyor. Ama kayıt
ekranda görülenden biraz daha fazla para ve XP biriktiriyor, enerji ödülleri de istemcinin gösterdiğinden başka
vuruşlarda düşüyor.

Küçük bir kenar durum da kaldı (YS-02): sunucunun "seviye 1" diye gönderdiği komşu/PvP filolarında Titan varsa iki
taraf Titan'ı farklı seviyeyle hesaplıyor.

Betikler `docs/denetim/hesap/yeniden-savas/` altında; depo kökünden
`../venv312/Scripts/python.exe docs/denetim/hesap/yeniden-savas/<betik>.py` ile çalışırlar ve depoda bir şey
değiştirmezler. Bütün testler geçiyor (`pytest -q`: 187 geçti).

## Bulgu bulgu durum

| Bulgu | Karar | Kanıt |
|---|---|---|
| SAV-01 Titan saldırı gücü | **Düzeldi** (kenar durum: YS-02) | `get_unit_attack_strength` (`battle_engine.py:1285`) `-attackStrength`'i okuyor; formül `A`=saldıranın, çarpan=savunanın saldırı gücü. İstemcide `BattleAI.GetAttackingDamage` 2-86 aynı: `GetAttackingStrengthAgainst(..,STRENGTH_MAX)` = `unitItem.getAttackStrength(fleet)`, çarpan `defender.unitItem.getAttackStrength(defender.fleet)`; `UnitItem.getAttackStrength` → `getXmlStrength(fleet,true)` → `entry.attackStrength`. `titan_guc.py`: 390/390 vuruş motor = istemci. Seviye: istemci `fleet.playerLevel` kullanıyor; Titan Lab'in BM03 filosu `BattleMechlab.createEnemyFleet` → `createFleet` ile kuruluyor, bu yüzden oyuncunun o anki seviyesi geçerli ve sunucuyla aynı. |
| SAV-02 Sersemletmede çökme | **Düzeldi** | `battle_engine.py:1229` `grade >= 0`; `FindBestDefendingUnitAgainstBestAttacker` gibi ikinci zar atılmıyor. `savas/kazalar.py` artık "cokmedi" diyor; `test_all_stunned_player_units_do_not_stop_the_ai` zar sayısını (2) denetliyor. |
| SAV-03 `round` / `Math.round` | **Düzeldi** | Savaş, bot, Titan, quest ve state_machine kodunda `round(` kalmadı; `as3_round` = `floor(x+0.5)`. İstemcide `findBestUnit` 225-243 ve `FindBestDefendingUnitAgainstAttackers` 255-279 `int(Math.round(r*(n-1)))`. `tur_uyumu.py 400 11`: 82 birim, 400 savaş, 7334 hamle, **0 ayrılık**. |
| SAV-04 Güçle öldürme ödülü | **Düzeldi ama yeni sorun çıktı (YS-01)** | Öldürmede ödül artık doğru tarafta: `kazalar.py` 2. bölümde oyuncu düşmanı öldürünce +18 para, +1 XP; düşman oyuncunun birimini öldürünce yalnız kayıp ganimeti. Öldürmeyen güç vuruşu ise istemcinin vermediği ödülü alıyor (YS-01). |
| SAV-05 Araştırma gücü yuvarlama | **Düzeldi** | `battle_engine.py:366-372`: her yükseltmeden sonra `as3_round`. `WorldUpgradeManager.getModifiedStrength` 64-112 aynı: yüzde ya da düz ekleme, ardından `Math.round`. Test: 90+%25 → 113, 80+%33 → 106. |
| SAV-06 Vuruş ödülü ve zar | **Birim vuruşlarında düzeldi; güç vuruşunda YS-01** | `doBattleRewards` (`battle_engine.py:1383`): her hasarlı vuruşta 1 zar, ustalık çarpanı 1 iken her `-percent`'li enerji ödülü için 1 zar daha. İstemci: `EnemyUnit.playDamageXPReward` 698 (`rewardInstance.float`, `getRandomRewards`'a verilir; o yöntem ve `DooberManager.shouldGiveReward` zar atmıyor), sonra `BattleUnit.addRewards` 221-254 (`currentMasteryScalar == 1 &&` `BattleUnit.shouldGiveReward`, o da zar atıyor). Öteki ödül zarları bu kurulumda kapalı: mana (`getManaLootDrop`, `empires_support_units_doober_drop` varyantı 0 → değer 0), beyaz birim (deney yok), `applyXPMultiplier` (`xp_multiplier: 1`). Sıyırarak öldürmede para yok, nadir kaynak türü saldıranın o anki gücünden (`onUnitHit` 815-835), `spawnLoot`'taki ustalık ölçekleme ve `PlayerUnit.playDamageXPReward` kayıp ganimeti (para + `getOilAmount` + ilk nadir maliyet ×1) koda uyuyor. |
| SAV-07 Eski istek cevabı | **Düzeldi** (güven: yüksek) | `no_data_response` (`empires-server.py:3153`) `data: None` dönüyor. `Transaction.onAmfComplete` 57-73 `data == null` iken `onComplete`'i çağırmıyor, `TResolveBattle`'ın denetimi ve hatası da çalışmıyor. `assignConsumable` için `[]` kalmış ama `TAssignConsumable.onComplete` yalnız üst sınıfı çağırıyor, bir şeyi denetlemiyor. |
| SAV-08 Savaş testleri | **Kısmen düzeldi** | Bkz. "Testlerin değeri". |
| SAV-09 Uçaksavar NPC çökmesi | **Düzeldi** | `battle_engine.py:598-603` zincirde olmayan tür için `good`; `CombatChain.getHitValue` 13-34 aynı (`chain == null` → `Chain.GOOD`). |
| SAV-10 İkinci yetenek sırası | **Düzeldi** | Ayrıntısı tablonun altında. |
| SAV-11 Bot dengesi belgesi | Kapsam dışı (yeniden ölçülüyor) | Test tarafı iyileşti: `test_the_battles_played_here_are_the_engines`, denge testindeki kopyanın 27 savaşta motorla aynı sonucu verdiğini denetliyor. |
| SAV-12 Bot dosyası, Titan parçası | **Düzeldi** | `_write_state` önce `.tmp`'ye yazıp `os.replace` ile yerine koyuyor; `invasion_complete` `.get` kullanıyor; `unlock_part` nakit denetliyor. Üçünün de testi var. |

**SAV-10 ayrıntısı.** `battle_engine.py:936-949` her düşman turunda n'inci "AI" isteğini n'inci yetenekli birime
veriyor. İstemciyle karşılaştırma:

- `BattleHost.state_UseSecondaryAbility` 29-252 düşman filosunun birimlerini sırayla geziyor. Yeteneği olan ve
  sersemlememiş her birim için bir `TAssignConsumable("AI")` gönderiyor ve
  `BattleAI.SecondaryAbilityHueristicsTarget`'te 1 zar atıyor (`r < castPercent`). Hedef bulunursa duruyor.
- Ölen birim filodan çıkıyor (`Battle.killUnit` 48-87). Yalnız `controller` türü (`UnitItem.MEGA_UNIT_CONTROLLER`)
  kalıyor; oyun verisinde yeteneği olan controller yok.
- Hedef seçen yardımcılar (`getBestUnitForAttackingPower`, `getBestUnitForFriendlyPower`, `getMostDamagedUnit`) zar
  atmıyor.
- İşaretler `consume_consumables` (`tries -1`) ile siliniyor. Bu, düşman saldırısında, hedefli düşman gücünde ve
  atlanan turda oluyor: `state_ChoosePlayerTarget` saldıran bulamayınca `updateConsumableSkipped(true)` →
  `TResolveBattle(..., aiAttack=true)` gönderiyor; bu istekte `id` yok, sunucu onu düşman turu sayıyor.

## Yeni bulgular

### YS-01 — Öldürmeyen güç vuruşu sunucuda ödül ve ödül zarı alıyor, istemcide almıyor
- **Önem:** Orta. **Güven:** kesin (istemci bytecode'u ve çalıştırma).
- **Yer:** `battle_engine.py:1127-1138` (`consumable_hit_rewards`); çağrıldığı yerler `1094` (doğrudan vuruş) ve
  `1123` (çevre hasarı).
- **Kanıt:** İstemcide `Battle.onUnitDamageFromConsumable` 487-545, `UNIT_HIT` olayına şunu koyuyor:
  `damage: target.unit.dead ? damage : false`. Ardından iki şey oluyor:
  - `BattleUnit.onUnitHit` olayı `playDamageXPReward`'a iletiyor.
  - `EnemyUnit.playDamageXPReward` 91-96, `if (!eventData.damage)` ise hemen dönüyor.

  Yani güç birimi öldürmezse istemci para, XP ya da enerji vermiyor ve `rewardInstance` zarını atmıyor. Sunucu her
  hasarlı güç vuruşunda `doBattleRewards("directhit", …)` çağırıyor:
  ```
  > python docs/denetim/hesap/yeniden-savas/guc_odulu.py
  == N04 olmeyen dusmana (U05, 100 guc)
    dusman gucleri [100, 100] -> [40.0, 100] | vurulan [0] olen []
    SUNUCU : para 5000 -> 5060 (+60) | xp +1 | odul tohumu degisti: True
    ISTEMCI: yalniz olen birimler icin odul ve zar -> HIC odul yok, odul zari atilmaz
  == N04 olduren vurus (U01, 30 guc)
    SUNUCU : para 5000 -> 5018 (+18) | xp +1 | odul tohumu degisti: True
    ISTEMCI: yalniz olen birimler icin odul ve zar -> olen 1 birim icin
  ```
  Öldüren vuruş istemciyle tutuyor. Küçük bir ek fark var: istemci düşmanı 1 güçte bırakmamak için hasara 1 ekliyor
  (`onUnitDamageFromConsumable` 330-384) ve parayı bu hasarla hesaplıyor; sunucu gücü 0'a çekiyor ama paraya eski
  hasarı veriyor.
- **Oyuncuya etkisi:**
  - Hava saldırısı ya da topçu baraj gibi bir güçle sağ kalan her düşman birimi için kayda ekranda hiç görünmeyen
    para ve 1 XP yazılıyor; örnekte 60 para. Çok hedefli ve çevre hasarlı güçlerde bu her birim için oluyor.
  - Sunucunun ödül tohumu her böyle vuruşta bir adım öne geçiyor. Aynı oturumda sonraki kritik vuruşlarda sunucunun
    verdiği enerji, istemcinin ekrana düşürdüğü enerjiden farklı çıkıyor.
  - Çökme ya da kayıp yok.
  - Bu davranış eski kodda yoktu: 61ac7a8 güçte hiç ödül zarı atmıyordu ve öldürmeyen vuruşta istemciyle aynıydı.
- **Öneri:**
  - `consumable_hit_rewards`'ta düşman tarafında yalnız `killed` iken `doBattleRewards("kill", …)` çağırın. Hasar
    olarak istemcinin kullandığını (1 güç bırakmama artışı dâhil) verin.
  - `battleDamage` görev ilerlemesinin güç vuruşunda sayılıp sayılmayacağı ayrı bir karar. İstemci bunu belirlemiyor,
    sunucuya kalmış.
  - Öldürmeyen güç vuruşu için "para yok, zar yok" testi ekleyin.

### YS-02 — Sunucunun "seviye 1" diye gönderdiği filolarda Titan'ın seviyesi iki tarafta farklı (SAV-01'den kalan)
- **Önem:** Düşük. **Güven:** mekanizma kesin; oyunda karşılaşma olası.
- **Yer:** `battle_engine.py:1291-1296`: Titan seviyesi her zaman `session` oyuncusunun seviyesi. Filoların gittiği
  yerler `empires-server.py:2296` (`random_fleet_challenge_response`, PvP savunma filosu) ve `2380`
  (`random_enemy_fleet_challenge_response`, işgal filosu); ikisi de `"playerLevel": 1` yazıyor.
- **Kanıt:** `UnitItem.getXmlStrength` 64-143 seviyeyi `fleet.playerLevel`'dan alıyor; `Fleet.<init>` 171-176 bunu
  sunucunun gönderdiği filo verisinden okuyor. Bu filolardaki düşman Titan'ı istemci 20. seviyenin altındaki ilk
  kademeyle, sunucu oyuncunun seviyesiyle hesaplıyor.
  `titan_guc.py`: düşman Titan vuruşlarının 153/195'i farklı hasar veriyor. Botların savunma havuzunda Titan yok
  (`bot_empires.DEFENDER_POOL`). Ama `invasion_complete` oyuncunun sağ kalan saldırı filosunu
  (`attacker_fleet`, Titan olabilir) öteki kayda yazıyor; o kayıt işgali püskürtürken bu filo seviye 1 ile gidiyor.
  Ayrıca istemcinin kendi kurduğu filo, kurulduğu andaki seviyeyi saklıyor: oturum içinde 20/30/40… eşiğini geçen
  oyuncunun eski filosundaki Titan'ı istemci bir kademe düşük hesaplar (olası; filonun yeniden kurulup kurulmadığına
  bakmadım).
- **Oyuncuya etkisi:** Yalnız iki yerel kayıtla PvP/işgal oynayan ve filosunda Titan olan oyuncuda, Titan'lı hamlelerde
  `ps/es` tutmaz ve istemci savaşı hata ile keser.
- **Öneri:** Bu filolarda `playerLevel`'ı sahibinin seviyesi olarak gönderin ve `get_unit_strength`'e aynı seviyeyi
  verin (ör. savaş başında `BattleContext`'e yazın).

## Testlerin değeri

- **`test_turns_follow_the_client` gerçekten değerli.** İstemcinin rastgele sayı üreticisini, yapay zekâsını ve
  hasarını bytecode'dan ayrıca yazıyor (`ClientRandom`, `client_ai`, `client_damage`). Her hamlede birimleri, zarı,
  güçleri ve tohumları karşılaştırıyor. Sınırları:
  - Zincir ve isabet tablosunu motordan alıyor (`get_combat_chain_grade`, `get_hit_value`).
  - 6 birimlik dar bir havuz kullanıyor: zayıf birim, araştırma, güç ve Titan yok.

  Benim `tur_uyumu.py` betiğim aynı modeli 82 birim ve 400 savaşla oynattı; ayrılık çıkmadı.
- **Titan, araştırma, zincir ve sersemletme testleri** istemciden türetilmiş sayıları denetliyor: 300/2400; 30 değil
  233; 113 ve 106; `good`; zar sayısı 2. SAV-01/02/03/05/09 geri gelirse kırılırlar.
- **Ödül testleri** zar sayısını ve parayı istemci kuralına göre denetliyor: sıyırarak öldürmede para yok,
  `criticalkill`'de 3 zar, ustalıkta enerji zarı yok. Ama güç tarafında yalnız öldüren vuruş test edilmiş. YS-01'i
  yakalayacak "öldürmeyen güç" testi yok; `battle_test.py`'ye eklenen kaynak alanları da yalnız eski güç testlerinin
  çökmemesi için, ödülü denetlemiyor.
- **İkinci yetenek testleri** sırayı, ölen birimi ve yeni turda başa dönmeyi denetliyor. Atlanan tur
  (`updateConsumableSkipped`), hedefli düşman gücünden sonra işaretlerin silinmesi ve sersemlemiş destek birimi
  durumları test edilmemiş.
- **Bot testi** artık kopyanın motorla aynı olduğunu motoru çalıştırarak gösteriyor (`engine_play`). Bu, SAV-08'in
  istediğiydi.

Sonuç: testlerin çoğu sunucu kodunu yeniden anlatmıyor, istemciden türetilmiş beklentiye bakıyor. Güç ödülü
testindeki boşluk, yanlış iddianın (YS-01) test kırmadan geçmesine izin verdi.

## Bakılamayanlar

- Oyunu istemciyle çalıştırıp denemedim; her şey bytecode okuması ve motoru doğrudan çağıran betiklerle yapıldı.
- Ödül zarı sayısı şu deney değerlerine bağlı: `empires_support_units_doober_drop` 0, beyaz birim deneyi yok,
  `xp_multiplier` 1, `ammo master` kapalı, `energyRewardModVariant` 0. Biri değişirse istemci fazladan zar atar.
- Süreli hasarla (DOT) ölen birimin ödülünü ve kayıp ganimetini istemciyle karşılaştırmadım; sunucu
  `apply_dot_damage`'da hiç ödül vermiyor.
- Sersemletme süresinin istemcide hangi turda bittiğini karşılaştırmadım. Süre bir tur kayarsa, yeni "AI" sayacı
  (`battle_engine.py:943-946`) eski koddan farklı olarak fazladan gelen "AI" isteğinde istisna atar (500). Bu bir
  tahmin, kanıtlanmış değil.
- `BM01-BM17` görev Titan filolarının istemcide hangi `playerLevel` ile kurulduğuna bakmadım.
- `get_mastery_scalar`'ın istemcinin `currentMasteryScalar`'ıyla aynı olduğunu varsaydım.
- Eski betiklerden `kazalar.py` yeniden çalıştırıldı ve geçerli. `titan_hasar.py`, `yuvarlama.py` ve
  `arastirma_gucu.py` eski sunucu formülünü kendi içinde taklit ediyor; bugünkü kodu ölçmedikleri için yerlerine
  `titan_guc.py` ve `tur_uyumu.py` yazıldı. Araştırma yuvarlaması testte doğrudan denetleniyor. 61ac7a8'in sunucu
  kodunu çalıştırmadım.
