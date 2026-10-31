"""Yuvarlama farki (yuvarlama.py) gercek savaslarda ne siklikla AI'nin sectigi birimi degistirir?

Ayni tohumla ayni savasi asil motorda iki kez oynatir: bir kez Python round() ile (bugunku sunucu), bir kez
battle_engine icinde round yerine AS3 Math.round (floor(x + 0.5)) ile (istemci). AI turlarindan biri farkli birim
cifti secerse istemci "unit IDs out of sync" hatasi verir (TResolveBattle.onComplete -> error -> TransactionFaultEvent).
Kullanim (depo kokunden): python docs/denetim/hesap/savas/yuvarlama_mac.py [mac_sayisi]
"""
import builtins
import contextlib
import io
import math
import os
import random
import sys

sys.argv = sys.argv[:2]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_denge as B  # noqa: E402  (oturum kurulumu ve takim cekimi)
from flask import session  # noqa: E402

battle_engine = B.battle_engine


def as3_round(x, *nd):
    return math.floor(x + 0.5) if not nd else builtins.round(x, *nd)


def play(player, enemy, seeds, as3):
    picks = []
    original = battle_engine.ai_best_attack

    def spy(*a):
        r = original(*a)
        picks.append((r[0], r[2]))
        return r
    battle_engine.ai_best_attack = spy
    if as3:
        battle_engine.round = as3_round
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            B.engine_battle(player, enemy, random.Random(seeds))
    finally:
        battle_engine.ai_best_attack = original
        if as3:
            del battle_engine.round
    return picks


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    rng = random.Random(11)
    differ = ai_turns = 0
    with B.T.app.test_request_context():
        session.sid = "0"
        for k in range(n):
            level = rng.randrange(10, 100, 10)
            pool = [i["-code"] for i in B.bot_empires.DEFENDER_POOL if level - 20 <= int(i["requiredLevel"]) <= level]
            player = [rng.choice(pool) for _ in range(rng.randint(3, 5))]
            B.setup(level, player)
            bot = B.bot_empires.bots()[rng.randrange(15)]
            enemy = [u.split(",")[0] for u in B.bot_empires.defense_fleet(bot)]
            seed = rng.randrange(2 ** 32)
            a, b = play(player, enemy, seed, False), play(player, enemy, seed, True)
            ai_turns += len(a)
            if a != b:
                differ += 1
    print("mac:", n, "AI turu:", ai_turns, "AI seciminin istemciden ayrildigi mac:", differ,
          "(%.2f%%)" % (100 * differ / n))


if __name__ == "__main__":
    main()
