"""Titan (ML..) birimlerinde sunucunun hasar hesabi istemciyle ayni mi?

Istemci (BattleAI.GetAttackingDamage + UnitItem.getAttackStrength/getXmlStrength):
  A = saldiranin getAttackStrength (Titan icin <strengths><entry attackStrength=..>)
  D = savunanin o anki gucu (Titan icin entry strength ile baslar)
  hasar = 25 * (3A + D) / (3D + A) / 100 * savunanin getAttackStrength
Sunucu (battle_engine.battle_complete_response): ayni formul, ama get_unit_max_strength Titan icin entry "strength"
dondurur; "attackStrength" hic okunmaz.
Kullanim (depo kokunden): python docs/denetim/hesap/savas/titan_hasar.py
"""
import contextlib
import copy
import io
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    from flask import Flask, session
    import battle_engine
    import titan_lab
    from game_settings import lookup_item_by_code
battle_engine.report_battle_log = lambda *a: None
app = Flask(__name__)
app.secret_key = "x"
INIT_USER = json.load(open(os.path.join(ROOT, "test", "init_user.json")))


def entry(code, level):
    entries = lookup_item_by_code(code)["unit"]["strengths"]["entry"]
    return next((e for e in entries if level < int(e["-level"])), entries[-1])


def client_damage(a_attack, d_current, d_attack):
    return math.floor(25 * (3 * a_attack + d_current) / (3 * d_current + a_attack) / 100 * d_attack * 1000) / 1000


LEVEL = 25
with app.test_request_context():
    session.sid = "0"
    session["user_object"] = copy.deepcopy(INIT_USER)
    session["user_object"]["userInfo"]["player"]["level"] = LEVEL
    session["user_object"]["userInfo"]["player"]["inventory"] = {"items": {}}
    session["quests"] = []
    session["fleets"] = {"fleet3_1": ["V06,150,0,0,0", "V06,150,0,1,0"]}
    session["battle"] = None
    with contextlib.redirect_stdout(io.StringIO()):
        titan_lab.status_response({"index": 2, "partsItemCode": "TL01"})
        params = {"fleet": "fleet3_1", "target": "fleet4_1", "map": None}
        friendlies, fs, baddies, bs, _ = battle_engine.init_battle(params)
    titan = baddies[0]["-code"]
    e = entry(titan, LEVEL)
    v06 = int(lookup_item_by_code("V06")["unit"]["-strength"])
    print("Titan", titan, "seviye", LEVEL, ": strength", e["-strength"], "attackStrength", e["-attackStrength"],
          "| sunucunun kullandigi en yuksek guc:", bs[0])
    # oyuncu vuruyor (V06 -> Titan), Titan tam gucte
    srv = math.floor(25 * (3 * v06 + bs[0]) / (3 * bs[0] + v06) / 100 * bs[0] * 1000) / 1000
    cli = client_damage(v06, int(e["-strength"]), int(e["-attackStrength"]))
    print("oyuncu -> Titan duz vurus hasari: sunucu", srv, "istemci", cli, "oran", round(srv / cli, 2))
    # Titan vuruyor (Titan -> V06), V06 tam gucte
    srv = math.floor(25 * (3 * bs[0] + v06) / (3 * v06 + bs[0]) / 100 * v06 * 1000) / 1000
    cli = client_damage(int(e["-attackStrength"]), v06, v06)
    print("Titan -> oyuncu duz vurus hasari: sunucu", srv, "istemci", cli, "oran", round(srv / cli, 2))

    # asil motorla: oyuncu Titanlara arka arkaya duz vuruslar yapsa sunucu Titanu kac vurusta oldurur?
    session["user_object"]["userInfo"]["world"]["randSeedW"] = 1
    session["user_object"]["userInfo"]["world"]["randSeedZ"] = 1
    hits = 0
    with contextlib.redirect_stdout(io.StringIO()):
        while session.get("battle") and session["battle"][1][0] > 0 and hits < 200:
            battle_engine.battle_complete_response(dict(params, id=[0, 0]))
            hits += 1
            if session.get("battle"):
                session["battle"][0][:] = [150, 150]  # oyuncu birimleri olmesin, yalniz oyuncu vuruslarini sayiyoruz
    left = int(e["-strength"])
    client_hits = 0
    while left > 0:
        left -= math.ceil(client_damage(v06, left, int(e["-attackStrength"])))
        client_hits += 1
    print("Titan'i oldurmek icin oyuncu vurusu: sunucu (asil motor, karisik isabetler)", hits,
          "| istemci (hep duz vurus)", client_hits)
