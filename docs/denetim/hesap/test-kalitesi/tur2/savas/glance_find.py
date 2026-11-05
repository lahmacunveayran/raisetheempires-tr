import math, sys
import client_settings as c
class T: pass
t = T()
t.LAND_POOL = ["U01", "U04", "U05", "V03", "V61", "V62", "ML11", "PU3", "PU4"]
t.cut_to_3 = lambda x: int(x * 1000) / 1000
def md(research, damage):
    for code in research:
        m = c.upgrade(code)
        if "damage" in m:
            damage = t.cut_to_3(damage + damage * float(m["damage"]) / 100) if m.get("percent") else damage + float(m["damage"])
    return damage
t.modified_damage = md
for a in t.LAND_POOL:
    for d in t.LAND_POOL:
        for left in (c.strength(d), 30, 20, 10):
            crit, direct = c.hit_value(a, d)
            if direct <= 0: continue
            res = ["XD01"]
            att = t.cut_to_3(c.attack_strength(a, 1, res)); l = t.cut_to_3(left)
            D = 25 * (3 * att + l) / (3 * l + att) / 100 * c.attack_strength(d, 1)
            dm = t.modified_damage(res, D); dm, up = t.cut_to_3(dm), t.cut_to_3(dm - D)
            g = c.game_number("combatGlancingBlowMultiplier")
            good = math.ceil(dm * g); good += (good - math.ceil(up * g) == 0)
            bad = math.ceil(dm * g); bad += (bad - math.ceil(up) == 0)
            if good != bad:
                print(a, d, left, D, good, bad, direct)
