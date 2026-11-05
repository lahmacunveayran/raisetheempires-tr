"""Python round() ile istemcinin Math.round()'u esitlik bozmada ayni birimi mi secer?

Istemci (BattleAI.findBestUnit / FindBestDefendingUnitAgainstAttackers): int(Math.round(r * (n - 1))),
r = ZGameRandom.float() (3 basamak). AS3 Math.round(x) = floor(x + 0.5) (yarim yukari).
Sunucu (battle_engine.ai_best_unit / ai_best_attack): round(r * (n - 1)) -> Python 3 "bankaci yuvarlamasi"
(yarim cifte: round(0.5) == 0, round(2.5) == 2).
Kullanim: python docs/denetim/hesap/savas/yuvarlama.py
"""
import math

for n in range(2, 6):
    bad = []
    for k in range(1000):
        r = k / 1000  # roll_random_float'in verebilecegi degerler (floor(x*1000)/1000)
        x = r * (n - 1)
        if round(x) != math.floor(x + 0.5):
            bad.append((r, round(x), math.floor(x + 0.5)))
    print("aday sayisi", n, ": farkli secim veren r degerleri", len(bad), "/ 1000 ->", bad)

# Mutteffik/paralı asker gucu (A0A): sunucu round(roll_random_between(0, len - 1)), istemci
# ConsumableItem.getRandomConsumableForLevel int(Math.round(randBetween(0, len - 1))). Ayni sorun, daha buyuk n.
print()
for n in (5, 10, 15, 20, 25, 30, 40):
    bad = sum(1 for k in range(1000) if round(k / 1000 * (n - 1)) != math.floor(k / 1000 * (n - 1) + 0.5))
    print("A0A aday sayisi", n, ": farkli secim olasiligi", bad / 1000)

# Gercek oyun verisiyle A0A aday sayisi (battle_engine.assign_consumable_response'taki suzgec, hasarli birim var)
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
items = json.load(open(os.path.join(ROOT, "gamesettings-converted.json"), encoding="utf-8"))["settings"]["items"]["item"]
cons = [c for c in items if c.get("-type") == "consumable" and c.get("-subtype") == "consumable"]
for level in (6, 15, 30, 60, 100):
    valid = [c for c in cons if "-secondary" not in c and int(c.get("requiredLevel", "0")) <= level
             and 'requiredDate' not in c and c["consumable"].get("-allypower", "true") != "false"]
    n = len(valid)
    bad = sum(1 for k in range(1000) if round(k / 1000 * (n - 1)) != math.floor(k / 1000 * (n - 1) + 0.5))
    print("seviye", level, "A0A aday:", n, "farkli secim olasiligi:", bad / 1000)
