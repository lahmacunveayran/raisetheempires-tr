"""Savas motorundaki cokme ve odul hatalarini asil kodla calistirarak gosterir.

1. Oyuncunun hayatta kalan butun birimleri sersemletilmisken (dusman N64 "stun") AI turu cokuyor.
2. Guc (consumable) ile oldurulen birimde odul ve "battleKill" ilerlemesi ters tarafa yaziliyor:
   oyuncu dusmani oldurunce bir sey almiyor, dusman oyuncunun birimini oldurunce oyuncu odul aliyor.
Kullanim (depo kokunden): python docs/denetim/hesap/savas/kazalar.py
"""
import contextlib
import copy
import io
import json
import os
import sys
import traceback

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


def fresh(player_codes, enemy_codes, battle=None):
    session.sid = "0"
    session["user_object"] = copy.deepcopy(INIT_USER)
    session["quests"] = []
    session["fleets"] = {"fleet2_1": [c + ",,,," for c in player_codes],
                         "fleet3_1": [{"-" + c: "1"} for c in enemy_codes]}
    session["battle"] = battle


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


with app.test_request_context():
    print("== 1. Butun oyuncu birimleri sersemlemisken AI turu")
    n64 = lookup_item_by_code("N64")
    # oyuncunun tek birimi kaldi (ikincisi olu) ve dusman US14'un N64'u ile sersemledi
    fresh(["U05", "U05"], ["US14", "U05"],
          ([100, 0], [None, None], [(n64, ("ally", 0), 5)], battle_engine.BattleContext()))
    s = session["battle"]
    s = ([100, 0], [quiet(battle_engine.get_unit_max_strength, lookup_item_by_code(c), False) for c in ("US14", "U05")],
         s[2], s[3])
    session["battle"] = s
    try:
        quiet(battle_engine.battle_complete_response, {"fleet": "fleet2_1", "target": "fleet3_1", "map": None})
        print("cokmedi")
    except Exception as e:
        print("COKTU:", type(e).__name__, e)
        print("".join(traceback.format_exc().splitlines(True)[-4:]))

    print("== 2. Guc ile oldurme odulu")
    # 2a: oyuncu N04 (hava saldirisi) ile 30 gucunde bir dusmani olduruyor
    fresh(["U05"], ["U01", "U05"])
    user = session["user_object"]["userInfo"]
    session["user_object"]["userInfo"]["player"]["inventory"] = {"items": {"N04": 5}}
    quiet(battle_engine.init_battle, {"fleet": "fleet2_1", "target": "fleet3_1", "map": None})
    coins0, xp0 = user["world"]["resources"]["coins"], user["player"]["xp"]
    meta = {}
    quiet(battle_engine.apply_consumable_direct_impact, meta, lookup_item_by_code("N04"), 0,
          [lookup_item_by_code("U01"), lookup_item_by_code("U05")], session["battle"][1], {}, False, [])
    print("oyuncu dusmani oldurdu: dusman gucleri", session["battle"][1], "| para", coins0, "->",
          user["world"]["resources"]["coins"], "| xp", xp0, "->", user["player"]["xp"])
    # 2b: dusman gucu (ayni yol, ally=True) oyuncunun birimini olduruyor
    friendly = [30]
    coins0, xp0 = user["world"]["resources"]["coins"], user["player"]["xp"]
    quiet(battle_engine.apply_consumable_direct_impact, meta, lookup_item_by_code("N04"), 0,
          [lookup_item_by_code("U01")], friendly, {}, True, [])
    print("dusman oyuncunun birimini oldurdu: oyuncu gucu", friendly, "| para", coins0, "->",
          user["world"]["resources"]["coins"], "| xp", xp0, "->", user["player"]["xp"])
