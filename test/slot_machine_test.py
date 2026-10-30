import copy
import json
import os

from flask import Flask, session

import slot_machine

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)


def setup_session(tokens=0):
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["cash"] = 100
    user["userInfo"]["player"]["inventory"] = {"items": {"GPTK": tokens} if tokens else {}}
    user["userInfo"]["world"]["resources"] = {"coins": 0, "energy": 0, "oil": 0, "wood": 0, "aluminum": 0,
                                              "copper": 0, "gold": 0, "iron": 0, "uranium": 0}
    user["experiments"] = {}
    session["user_object"] = user
    session["quests"] = []
    return user


def items(user):
    return user["userInfo"]["player"]["inventory"]["items"]


def test_prizes_come_from_the_featured_set():
    with app.test_request_context():
        setup_session()
        loot = slot_machine.prizes()
        assert len(loot) == 15
        assert ("coins", 20000, 15) in loot and ("EN6", 5, 12) in loot
        assert loot[-1] == ("UG15", 1, 1)  # the grand prize is the rarest


def test_spin_with_tokens():
    with app.test_request_context():
        user = setup_session(tokens=7)
        loot = slot_machine.spin_response(slot_machine.MODE_KEYS)["data"]["loot"]
        assert items(user)["GPTK"] == 2
        if loot["handler"] == "addLootToInventory":
            assert items(user)[loot["payload"]["code"]] == loot["payload"]["quantity"]
        else:
            assert user["userInfo"]["world"]["resources"][loot["loot"]] == loot["payload"]["yield"]


def test_spin_with_cash():
    with app.test_request_context():
        user = setup_session()
        slot_machine.spin_response(slot_machine.MODE_BUY)
        assert user["userInfo"]["player"]["cash"] == 99
