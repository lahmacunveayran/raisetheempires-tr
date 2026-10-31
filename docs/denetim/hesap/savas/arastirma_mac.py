"""Arastirma guc yukseltmesinin yuvarlama farki (arastirma_gucu.py) savasi istemciden ayirir mi?

Ayni tohumla ayni savasi asil motorda iki kez oynatir: bugunku sunucu (guc * (1 + p/100), yuvarlamasiz) ve istemcinin
hesabi (Math.round(guc + guc * p / 100), WorldUpgradeManager.getModifiedStrength). Oyuncunun birimlerine kademelerine
gore XS0<kademe> guc arastirmasi verilir. AI'nin sectigi birimler ya da savas sonucu farkliysa sunucu ile istemci
ayrismistir. Kullanim (depo kokunden): python docs/denetim/hesap/savas/arastirma_mac.py [mac_sayisi]
"""
import contextlib
import io
import math
import os
import random
import sys

sys.argv = sys.argv[:2]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_denge as B  # noqa: E402
from flask import session  # noqa: E402

be = B.battle_engine
server_upgrades = be.handle_strength_upgrades


def client_upgrades(strength, unit):
    research = session['user_object']["userInfo"]["world"]["research"]
    for upgrade in research.get(unit["-code"], []):
        mod = be.lookup_item_by_code(upgrade)["modifier"]
        if mod.get("-strength"):
            if mod.get("-percent"):
                strength = math.floor(strength + strength * float(mod["-strength"]) / 100 + 0.5)
            else:
                strength = math.floor(strength + int(mod["-strength"]) + 0.5)
    return strength


def play(player, enemy, seed, client):
    picks = []
    original = be.ai_best_attack

    def spy(*a):
        r = original(*a)
        picks.append((r[0], r[2]))
        return r
    be.ai_best_attack = spy
    be.handle_strength_upgrades = client_upgrades if client else server_upgrades
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            won = B.engine_battle(player, enemy, random.Random(seed))
    finally:
        be.ai_best_attack = original
        be.handle_strength_upgrades = server_upgrades
    return picks, won


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    rng = random.Random(5)
    pool = [i for i in B.bot_empires.DEFENDER_POOL if int(i["unit"].get("-tier", "1")) in (2, 3, 4)]
    differ = outcome = 0
    with B.T.app.test_request_context():
        session.sid = "0"
        for _ in range(n):
            units = [rng.choice(pool) for _ in range(rng.randint(3, 5))]
            level = max(int(u["requiredLevel"]) for u in units)
            player = [u["-code"] for u in units]
            B.setup(level, player)
            session['user_object']["userInfo"]["world"]["research"] = {
                u["-code"]: ["XS0%s" % u["unit"].get("-tier", "1")] for u in units}
            bot = B.bot_empires.bots()[rng.randrange(15)]
            enemy = [u.split(",")[0] for u in B.bot_empires.defense_fleet(bot)]
            seed = rng.randrange(2 ** 32)
            a, b = play(player, enemy, seed, False), play(player, enemy, seed, True)
            differ += a != b
            outcome += a[1] != b[1]
    print("mac:", n, "| AI secimi ya da sonucu istemciden ayrilan:", differ, "(%.1f%%)" % (100 * differ / n),
          "| kazanan taraf degisen:", outcome)


if __name__ == "__main__":
    main()
