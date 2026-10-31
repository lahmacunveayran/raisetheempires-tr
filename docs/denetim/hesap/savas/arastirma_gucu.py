"""Arastirma guc yukseltmesi (XS01-XS08, TS01-TS08): sunucu ve istemci ayni gucu mu hesaplar?
Istemci WorldUpgradeManager.getModifiedStrength: s = Math.round(s + s * mod / 100) (her yukseltmeden sonra yuvarlar).
Sunucu battle_engine.handle_strength_upgrades: s *= 1 + mod / 100 (yuvarlamaz).
Yukseltmeyi birimin kademesine (tier) gore esledik: XS0<tier> (kademesi olmayan birim: 1). Kullanim: depo kokunden."""
import json, math, collections
g = json.load(open("gamesettings-converted.json", encoding="utf-8"))
items = g["settings"]["items"]["item"]
mods = {i["-code"]: int(i["modifier"]["-strength"]) for i in items
        if isinstance(i.get("modifier"), dict) and "-strength" in i["modifier"]}
units = [i for i in items if isinstance(i.get("unit"), dict) and str(i["unit"].get("-strength", "")).isdigit()
         and i.get("-subtype") in ("army", "air", "navy") and i.get("-buyable") == "true"]
diff = collections.Counter(); total = collections.Counter(); ex = []
for u in units:
    tier = int(u["unit"].get("-tier", "1"))
    code = "XS0%d" % min(tier, 8)
    s = int(u["unit"]["-strength"]); p = mods[code]
    server = s * (1 + p / 100)
    client = math.floor(s + s * p / 100 + 0.5)  # AS3 Math.round
    total[code] += 1
    if server != client:
        diff[code] += 1
        if len(ex) < 8: ex.append((u["-code"], s, code, round(server, 4), client))
for code in sorted(total):
    print(code, "+%d%%" % mods[code], ": farkli", diff[code], "/", total[code])
print("ornekler (birim, guc, yukseltme, sunucu, istemci):", ex)
