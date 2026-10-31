"""Bot dengesi iddialarini yeniden turetir (bot_empires.py docstring ve test/bot_empires_test.py).

1. Testin kendi savas benzetimi (test/bot_empires_test.battle) ile asil motoru (battle_engine.battle_complete_response)
   ayni takimlarla, ayni oyuncu stratejisiyle oynatir; kazanma oranlarini adim adim yan yana yazar.
2. HANDICAP=0 iken oyuncu seviyesindeki botun (tam ayna) kazanma oranini olcer ("about 63%" iddiasi).
3. Testin 18 takimlik orneginin tohuma gore ne kadar oynadigini olcer.

Kullanim (depo kokunden): python docs/denetim/hesap/savas/bot_denge.py [takim_sayisi_seviye_basina] [mac_sayisi] [tohum]
(3. bolum, 13 tohum, uzun surer: ancak 4. arguman "yayilim" verilirse calisir)
Depoda hicbir seyi degistirmez: bot durum dosyasi ve kayitlar gecici klasore yonlendirilir.
"""
import contextlib
import copy
import io
import json
import math
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "test"))
os.chdir(ROOT)

with contextlib.redirect_stdout(io.StringIO()):
    from flask import session
    import battle_engine
    import bot_empires
    import bot_empires_test as T  # testin benzetimi: T.battle

TMP = tempfile.mkdtemp()
bot_empires.STATE_PATH = os.path.join(TMP, "bot_empires.json")
bot_empires.get_saves = lambda: []
battle_engine.report_battle_log = lambda *a: None
with open(os.path.join(ROOT, "test", "init_user.json")) as f:
    INIT_USER = json.load(f)
GRADES = bot_empires.GRADES


def setup(level, units):
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    objects = user["userInfo"]["world"]["objects"]
    objects[:] = [o for o in objects if o.get("itemName") not in bot_empires.UNITS_BY_NAME]
    objects += [{"itemName": bot_empires.lookup_item_by_code(code)["-name"]} for code in units]
    session["user_object"] = user
    session["quests"] = []


def kind(code):
    return T.kind(code)


def strength(code):
    return T.strength(code)


def engine_battle(player_codes, bot_codes, rng):
    """Ayni oyuncu stratejisi (testteki: beklenen pay en buyuk vurus), sonuclari asil motor hesaplar."""
    session["user_object"]["userInfo"]["world"]["randSeedW"] = rng.randrange(1, 2 ** 32)
    session["user_object"]["userInfo"]["world"]["randSeedZ"] = rng.randrange(1, 2 ** 32)
    session["fleets"] = {"fleet2_1": [c + ",,,," for c in player_codes],
                         "fleet3_1": [{"-" + c: "1"} for c in bot_codes]}
    session["battle"] = None
    player = [(kind(c), strength(c)) for c in player_codes]
    bot = [(kind(c), strength(c)) for c in bot_codes]

    def expected(attacker, defender, defender_left):
        critical, direct = battle_engine.get_hit_value(attacker[0], defender[0])
        crit = max(0.0, 1 - critical)
        mean = direct * 0.1 + (1 - direct - crit) + crit * 1.5
        return mean * 25 * (3 * attacker[1] + defender_left) / (3 * defender_left + attacker[1]) / 100 * defender[1]

    p_left, b_left = [s for _, s in player], [s for _, s in bot]
    for turn in range(500):
        players = [i for i, s in enumerate(p_left) if s > 0]
        bots = [i for i, s in enumerate(b_left) if s > 0]
        if not bots or not players:
            return bool(players)
        params = {"fleet": "fleet2_1", "target": "fleet3_1", "map": None}
        if turn % 2 == 0:
            a, d = max(((a, d) for a in players for d in bots),
                       key=lambda p: (min(1, expected(player[p[0]], bot[p[1]], b_left[p[1]]) / b_left[p[1]]),
                                      -b_left[p[1]]))
            params["id"] = [a, d]
        r = battle_engine.battle_complete_response(params)["data"]
        if session.get("battle"):
            p_left, b_left = list(session["battle"][0]), list(session["battle"][1])
        else:  # savas bitti: motor oturumu sifirladi
            if turn % 2 == 0:
                b_left[r["enemyUnit"]] = r["es"]
            else:
                p_left[r["playerUnit"]] = r["ps"]
    return sum(p_left) > sum(b_left)


def squads(rng, per_level, levels=range(10, 100, 10)):
    out = []
    for level in levels:
        for _ in range(per_level):
            pool = [i["-code"] for i in bot_empires.DEFENDER_POOL if level - 20 <= int(i["requiredLevel"]) <= level]
            out.append((level, [rng.choice(pool) for _ in range(rng.randint(3, 5))]))
    return out


def rates(squad_list, games, rng, use_engine, bots=None):
    n = len(bot_empires.DELTAS)
    wins, total = [0] * n, [0] * n
    for level, units in squad_list:
        setup(level, units)
        for i, bot in enumerate(bots or bot_empires.bots()):
            fleet = [u.split(",")[0] for u in bot_empires.defense_fleet(bot)]
            for _ in range(games):
                if use_engine:
                    with contextlib.redirect_stdout(io.StringIO()):
                        won = engine_battle(units, fleet, rng)
                else:
                    won = T.battle([(kind(u), strength(u)) for u in units], [(kind(u), strength(u)) for u in fleet], rng)
                wins[i // 3] += won
                total[i // 3] += 1
    return [round(w / t, 3) if t else None for w, t in zip(wins, total)]


def main():
    per_level = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    app = T.app
    with app.test_request_context():
        session.sid = "0"
        print("STRENGTH_PER_LEVEL =", round(bot_empires.STRENGTH_PER_LEVEL, 4),
              " HANDICAP faktoru =", round(bot_empires.STRENGTH_PER_LEVEL ** -bot_empires.HANDICAP, 3))
        sq = squads(random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 2024), per_level)
        print("takim sayisi:", len(sq), " takim x bot basina mac:", games)
        print("test benzetimi  (5 adim):", rates(sq, games, random.Random(1), False))
        print("asil motor      (5 adim):", rates(sq, games, random.Random(1), True))
        # tam ayna: HANDICAP=0, oyuncu seviyesindeki botlar (6,7,8)
        saved = bot_empires.HANDICAP
        bot_empires.HANDICAP = 0
        equal = bot_empires.bots()[6:9]
        n = len(bot_empires.DELTAS)
        r_sim = rates(sq, games, random.Random(3), False, bots=equal)
        r_eng = rates(sq, games, random.Random(3), True, bots=equal)
        print("HANDICAP=0, esit seviye botu: oyuncu kazanma (benzetim / motor):", r_sim[0], "/", r_eng[0],
              " -> botun kazanma:", round(1 - r_sim[0], 3), "/", round(1 - r_eng[0], 3))
        bot_empires.HANDICAP = saved
        if "yayilim" not in sys.argv:
            return
        # testin kendisi: 18 takim, 20 mac, 13 tohum
        spread = []
        for seed in range(13):
            rng = random.Random(seed)
            s = squads(rng, 2)
            spread.append(rates(s, 20, rng, False))
        for step in range(n):
            vals = [r[step] for r in spread]
            print("test ornegi adim", step, "tohumlar arasi min-max:", min(vals), "-", max(vals))


if __name__ == "__main__":
    main()
