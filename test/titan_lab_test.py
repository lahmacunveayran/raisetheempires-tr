import copy
import json
import os

from flask import Flask, session

import battle_engine
import titan_lab

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

LAB_ID = 7
OWN_FLEET = "fleet3_1"
ENEMY = "fleet4_1"


def setup_session():
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["cash"] = 100
    user["userInfo"]["player"]["inventory"] = {"items": {}}
    user["userInfo"]["world"]["objects"] = [{"id": LAB_ID, "itemName": "MechLab", "position": "10,10,0", "state": "11"}]
    user["experiments"] = {}
    session["user_object"] = user
    session["quests"] = []
    session["fleets"] = {OWN_FLEET: ["V06,180,1,0,0", "V06,180,1,1,0"]}
    session["battle"] = None
    return user


def lab(user):
    return user["userInfo"]["world"]["objects"][0]


def items(user):
    return user["userInfo"]["player"]["inventory"]["items"]


def test_parts_and_counts():
    with app.test_request_context():
        user = setup_session()
        parts = titan_lab.parts()
        assert [p["-code"] for p in parts] == ["B281", "B280", "B287", "B285", "B286", "B284", "B282", "B283"]
        assert titan_lab.part_count(parts[0]) == 10
        user["experiments"]["empire_mech_lab_01_parts"] = 5
        assert titan_lab.part_count(parts[0]) == 6


def test_part_unlocked_for_cash_is_kept():
    with app.test_request_context():
        user = setup_session()
        response = titan_lab.action_response("partUnlock", LAB_ID, {"partCode": "B280"}, {})
        assert response["data"] == {"id": LAB_ID}  # the world log reads it
        assert lab(user)["data"]["partUnlocks"] == {"B280": True}
        assert user["userInfo"]["player"]["cash"] == 80
        titan_lab.action_response("partUnlock", LAB_ID, {"partCode": "B280"}, {})  # already open
        titan_lab.action_response("partUnlock", LAB_ID, {"partCode": "B281"}, {})  # never locked
        assert user["userInfo"]["player"]["cash"] == 80


def test_collecting_a_part_unlocks_the_next():
    with app.test_request_context():
        user = setup_session()
        items(user).update({"B281": 10, "B280": 9})
        titan_lab.action_response("updatePartUnlocks", LAB_ID, {}, {})
        assert lab(user)["data"]["partUnlocks"] == {"B280": True}
        items(user)["B280"] = 10
        titan_lab.action_response("updatePartUnlocks", LAB_ID, {}, {})
        assert lab(user)["data"]["partUnlocks"] == {"B280": True, "B287": True}


def start_battle(index=2):
    titan_lab.status_response({"index": index, "partsItemCode": "TL01"})
    return battle_engine.init_battle({"id": [0, 0], "fleet": OWN_FLEET, "target": ENEMY, "ch": 1, "map": None})


def test_titan_battle_uses_the_titan_fleet():
    with app.test_request_context():
        setup_session()
        friendlies, friendly_strengths, baddies, baddie_strengths, _ = start_battle()
        assert [b["-code"] for b in baddies] == ["ML11", "ML15", "ML07", "ML13", "ML09"]
        assert [f["-code"] for f in friendlies] == ["V06", "V06"]
        assert len(baddie_strengths) == 5 and all(baddie_strengths)


def test_titan_units_grow_with_the_player_level():
    with app.test_request_context():
        user = setup_session()
        user["userInfo"]["player"]["level"] = 25
        assert battle_engine.get_unit_max_strength(battle_engine.lookup_item_by_code("ML11"), False) == 2400
        user["userInfo"]["player"]["level"] = 85
        assert battle_engine.get_unit_max_strength(battle_engine.lookup_item_by_code("ML11"), False) == 6000


def test_won_titan_battle_gives_the_part():
    with app.test_request_context():
        user = setup_session()
        friendlies, friendly_strengths, baddies, baddie_strengths, _ = start_battle(index=2)
        params = {"fleet": OWN_FLEET, "target": ENEMY, "map": None}
        battle_engine.handle_win([0] * len(baddie_strengths), {}, params, friendlies, friendly_strengths)
        assert items(user) == {"B287": 3}
        assert session["mechlab"] is None and not titan_lab.is_battle(params)


def test_lost_titan_battle_gives_nothing():
    with app.test_request_context():
        user = setup_session()
        start_battle()
        battle_engine.handle_loss([0, 0])
        assert session["mechlab"] is None and ENEMY not in session["fleets"]
        assert items(user) == {}


def test_retreat_and_fight_again():
    with app.test_request_context():
        setup_session()
        start_battle(index=1)
        session["battle"] = None  # retreated
        _, _, baddies, _, _ = start_battle(index=1)
        assert len(baddies) == 5 and session["mechlab"] == {"prize": "B280", "fleet": ENEMY}


def test_other_battles_are_left_alone():
    with app.test_request_context():
        setup_session()
        titan_lab.register_enemy_fleet({"fleet": OWN_FLEET, "target": "Q6016"})
        assert "Q6016" not in session["fleets"]
        assert not titan_lab.is_battle({"fleet": OWN_FLEET, "target": ENEMY})


def test_titan_name_is_kept():
    with app.test_request_context():
        user = setup_session()
        assert titan_lab.name_response("Demir Dev")["data"] == {"name": "Demir Dev"}
        assert user["userInfo"]["titanName"] == "Demir Dev"
