"""Siradan savaslarda gerileme var mi: sunucunun her hamlesini istemcinin hesabiyla karsilastirir.

test/battle_turn_test.py icindeki istemci modelini (ClientRandom, client_ai, client_damage; ZGame bytecode'undan
yazilmis) kullanir ama testteki 6 birimlik havuz yerine oyun verisindeki butun "zayif" olmayan, -strength'i olan,
ikincil yetenegi olmayan kara/deniz/hava birimleriyle ve testten cok daha fazla savasla oynar.
Her hamlede playerUnit, enemyUnit, ur, ps, es ve seeds istemcininkiyle ayni olmali.

Kullanim (depo kokunden): ../venv312/Scripts/python.exe docs/denetim/hesap/yeniden-savas/tur_uyumu.py [savas] [tohum]
"""
import contextlib
import io
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "test"))
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import battle_turn_test as T
    import battle_engine
    from game_settings import game_settings
    from flask import session


class Patch:
    def setattr(self, obj, name, value):
        setattr(obj, name, value)


chain_kinds = {c["-type"] for c in game_settings["settings"]["combatChain"]["chain"]}
pool = []
for i in game_settings["settings"]["items"]["item"]:
    u = i.get("unit")
    if not isinstance(u, dict) or "-strength" not in u or "-secondary" in u or u.get("-weak"):
        continue
    if i["-code"][0] not in "UVS" or not i["-code"][1:].isdigit():
        continue
    if u.get("-type", "").split(",")[0] not in chain_kinds:
        continue
    pool.append(i["-code"])

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 11)
mismatch = turns = battles = 0
first = None
with T.app.test_request_context(), contextlib.redirect_stdout(io.StringIO()):
    for b in range(N):
        terrain = rng.choice(["land", "sea", "air"])
        side = [c for c in pool if battle_engine.lookup_item_by_code(c)["unit"]["-type"].split(",")[1] == terrain] or pool
        players = [rng.choice(side) for _ in range(rng.randint(1, 5))]
        enemies = [rng.choice(side) for _ in range(rng.randint(1, 5))]
        user = T.setup(Patch(), players, enemies)
        world = user["userInfo"]["world"]
        world["randSeedW"], world["randSeedZ"] = rng.randrange(1, 2 ** 32), rng.randrange(1, 2 ** 32)
        client = T.ClientRandom(world["randSeedW"], world["randSeedZ"])
        pl, el = [T.strength(c) for c in players], [T.strength(c) for c in enemies]
        battles += 1
        for turn in range(80):
            if turn % 2 == 0:
                a = rng.choice([i for i, s in enumerate(pl) if s > 0])
                d = rng.choice([i for i, s in enumerate(el) if s > 0])
                r = battle_engine.battle_complete_response(dict(T.PARAMS, id=[a, d]))["data"]
                roll = client.float()
                el[d] -= T.client_damage(players[a], enemies[d], el[d], roll)
                el[d] = 0 if el[d] <= 1 else el[d]
            else:
                r = battle_engine.battle_complete_response(dict(T.PARAMS))["data"]
                d, a = T.client_ai(client, enemies, el, players, pl)
                roll = client.float()
                pl[a] = max(0, pl[a] - T.client_damage(enemies[d], players[a], pl[a], roll))
            turns += 1
            ok = ((r["playerUnit"], r["enemyUnit"], r["ur"]) == (a, d, roll) and (r["ps"], r["es"]) == (pl[a], el[d])
                  and r["seeds"] == {"w": client.w, "z": client.z})
            if not ok:
                mismatch += 1
                first = first or (players, enemies, turn, r, (a, d, roll, pl, el))
                break
            if not any(pl) or not any(el):
                break
print("birim havuzu:", len(pool), "| savas:", battles, "| hamle:", turns, "| istemciden ayrilan savas:", mismatch)
if first:
    print("ilk ayrilik:", first)
