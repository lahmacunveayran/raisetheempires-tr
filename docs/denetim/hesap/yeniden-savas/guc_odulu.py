"""Guc (consumable) isabetinin odulu: sunucu ile istemci karsilastirmasi.

Istemci (Battle.onUnitDamageFromConsumable, bytecode 515-540) UNIT_HIT olayina
    damage: target.unit.dead ? damage : false
koyar. EnemyUnit.playDamageXPReward ve PlayerUnit.playDamageXPReward ilk is `if (!eventData.damage) return` yapar
(bytecode 91-96 / 30-35). Yani guc birimi OLDURMEDIKCE istemci ne odul verir ne de odul zarini
(ZGameRandom.rewardInstance) atar. Bu betik sunucunun ayni durumda ne yaptigini asil kodla gosterir.

Kullanim (depo kokunden): ../venv312/Scripts/python.exe docs/denetim/hesap/yeniden-savas/guc_odulu.py
Depoda hicbir seyi degistirmez (oturum bellekte, test_request_context icinde).
"""
import contextlib
import copy
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    from flask import Flask, session
    import battle_engine
    from game_settings import lookup_item_by_code

battle_engine.report_battle_log = lambda *a: None
app = Flask(__name__)
app.secret_key = "x"
INIT_USER = json.load(open(os.path.join(ROOT, "test", "init_user.json")))


def fresh(player_codes, enemy_codes):
    session.sid = "0"
    session["user_object"] = copy.deepcopy(INIT_USER)
    session["user_object"]["userInfo"]["world"]["research"] = {}
    session["quests"] = []
    session["fleets"] = {"fleet2_1": [c + ",,,," for c in player_codes],
                         "fleet3_1": [{"-" + c: "1"} for c in enemy_codes]}
    session["battle"] = None


def snapshot():
    u = session["user_object"]["userInfo"]
    w = u["world"]
    return (w["resources"]["coins"], u["player"]["xp"], w["rewardRandSeedW"], w["rewardRandSeedZ"])


def run(title, player_codes, enemy_codes, code, target, start=None):
    fresh(player_codes, enemy_codes)
    session["user_object"]["userInfo"]["player"]["inventory"]["items"][code] = 1
    with contextlib.redirect_stdout(io.StringIO()):
        battle_engine.init_battle({"fleet": "fleet2_1", "target": "fleet3_1", "map": None})
    if start:
        b = session["battle"]
        session["battle"] = (b[0], list(start), b[2], b[3])
    before_strengths = list(session["battle"][1])
    c0, x0, w0, z0 = snapshot()
    with contextlib.redirect_stdout(io.StringIO()):
        battle_engine.assign_consumable_response({"id": target, "level": 0, "name": "fleet3_1", "fleet": None,
                                                  "map": None, "code": code})
    c1, x1, w1, z1 = snapshot()
    after = list(session["battle"][1]) if session["battle"] else list(session["last_battle"][1])
    killed = [i for i, (a, b) in enumerate(zip(before_strengths, after)) if a > 0 and b == 0]
    hit = [i for i, (a, b) in enumerate(zip(before_strengths, after)) if b < a]
    print("==", title)
    print("  dusman gucleri", before_strengths, "->", after, "| vurulan", hit, "olen", killed)
    print("  SUNUCU : para", c0, "->", c1, "(+%d)" % (c1 - c0), "| xp +%d" % (x1 - x0),
          "| odul tohumu degisti:", (w0, z0) != (w1, z1))
    print("  ISTEMCI: yalniz olen birimler icin odul ve zar ->", "olen %d birim icin" % len(killed) if killed
          else "HIC odul yok, odul zari atilmaz")


with app.test_request_context():
    # N04 hava saldirisi: 30 x 2 (kara) = 60 hasar; U05 (tank, 100 guc) olmez
    run("N04 olmeyen dusmana (U05, 100 guc)", ["U05"], ["U05", "U05"], "N04", 0)
    # ayni guc oldurunce: istemci de odul verir, sayilar tutmali
    run("N04 olduren vurus (U01, 30 guc)", ["U05"], ["U01", "U05"], "N04", 0)
