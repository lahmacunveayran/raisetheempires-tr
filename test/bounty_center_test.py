import copy
import json
import os
import time

from flask import Flask, session

import bounty_center

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

NOW = 1_800_000_000


def setup_session(monkeypatch, level=30, opponents=()):
    monkeypatch.setattr(bounty_center, "_now", lambda: NOW)
    monkeypatch.setattr(bounty_center.bot_empires, "get_saves", lambda: [
        {"user_object": {"userInfo": {"player": {"uid": uid, "level": lvl}}}} for uid, lvl in opponents])
    user = copy.deepcopy(INIT_USER)
    player = user["userInfo"]["player"]
    player["cash"] = 100
    player["level"] = level
    player["energy"] = 50
    player["lastEnergyCheck"] = time.time()  # no refill during the test
    player["inventory"] = {"items": {}}
    user["userInfo"]["world"]["resources"] = {"coins": 0, "energy": 50, "oil": 0, "wood": 0, "aluminum": 0,
                                              "copper": 0, "gold": 0, "iron": 0, "uranium": 0}
    user["experiments"] = {}
    session["user_object"] = user
    session["quests"] = []
    return user


def items(user):
    return user["userInfo"]["player"]["inventory"]["items"]


def test_energy_by_level(monkeypatch):
    with app.test_request_context():
        for level, energy in ((20, 6), (35, 6), (36, 8), (85, 10)):
            setup_session(monkeypatch, level=level)
            assert bounty_center.energy_required() == energy


def test_players_past_level_20_get_the_building_quest_once(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch, level=85)
        new_quests = []
        bounty_center.update_bounty_center(user, new_quests, {})
        assert [q["name"] for q in new_quests] == ["QBCB_1a", "QBCB_1b"]
        assert items(user)["BCB"] == 1
        session["quests"][:] = new_quests
        again = []
        bounty_center.update_bounty_center(user, again, {})
        assert again == []


def test_activate_and_skip_cooling(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch)
        response = bounty_center.action_response(bounty_center.STEP, 7, {"skipCooling": False}, {})
        assert response["data"] == {"id": 7}
        player = user["userInfo"]["player"]
        assert player["energy"] == 50 - 6 and player["cash"] == 100
        assert player["bountyCenter"]["lastActivated"] == NOW and bounty_center.is_active()
        bounty_center.action_response(bounty_center.STEP, 7, {"skipCooling": True}, {})
        assert player["energy"] == 50 - 12 and player["cash"] == 100 - 12


def test_bonds_only_while_active_against_close_players(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch, level=30, opponents=[(5, 20), (6, 19)])
        bounty_center.battle_won(5, {})
        assert "xk01" not in items(user)  # not activated
        bounty_center.action_response(bounty_center.STEP, 7, {}, {})
        bounty_center.battle_won(6, {})  # 11 levels below
        bounty_center.battle_won(9, {})  # unknown player
        assert "xk01" not in items(user)
        bounty_center.battle_won(5, {})
        assert items(user)["xk01"] == 1
        assert user["userInfo"]["player"]["bountyCenter"]["bountyBonds"] == 1
        monkeypatch.setattr(bounty_center, "_now", lambda: NOW + bounty_center.ACTIVE_PERIOD)
        bounty_center.battle_won(5, {})
        assert items(user)["xk01"] == 1  # the hour is over


def test_bot_empires_pay_bonds(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch, level=85)
        bounty_center.action_response(bounty_center.STEP, 7, {}, {})
        bounty_center.battle_won(bounty_center.bot_empires.FIRST_UID, {})  # the lowest bot: level 83
        assert items(user)["xk01"] == 1
