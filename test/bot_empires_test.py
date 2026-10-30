import copy
import json
import os

from flask import Flask, session

import bot_empires

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)


def setup_session(monkeypatch, tmp_path, level=85):
    monkeypatch.setattr(bot_empires, "STATE_PATH", str(tmp_path / "bot_empires.json"))
    monkeypatch.setattr(bot_empires, "get_saves", lambda: [])
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    session["user_object"] = user
    return user


def test_fight_list_follows_the_player_level(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path)
        data = bot_empires.fight_list()
        assert len(data["fightList"]) == 15  # GlobalPVPMaxInvasionSlots
        assert sorted({i["level"] for i in data["info"]}) == [83, 84, 85, 87, 89]
        assert all(i["snUser"]["name"] and i["snUser"]["image"].startswith("img/avatars/") for i in data["info"])
        assert len({i["uid"] for i in data["info"]}) == 15
        setup_session(monkeypatch, tmp_path, level=1)
        assert min(i["level"] for i in bot_empires.fight_list()["info"]) == 1


def test_bots_defend_with_units_of_their_level(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path, level=40)
        for bot in bot_empires.bots():
            fleet = bot_empires.defense_fleet(bot)
            assert len(fleet) == bot_empires.DEFENDERS
            for unit in fleet:
                item = bot_empires.lookup_item_by_code(unit.split(",")[0])
                assert item["-subtype"] == "army" and int(item["requiredLevel"]) <= bot_empires.level(bot)


def test_bot_saves_keep_invasions(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path)
        uid = bot_empires.bots()[3]["uid"]
        save = bot_empires.find_save(uid)
        assert save["bot"] and save["user_object"]["userInfo"]["world"]["objects"]
        save["user_object"]["pvp"]["invaders"]["u1"] = {"status": 1}
        bot_empires.store_save(save)
        assert bot_empires.find_save(str(uid))["user_object"]["pvp"]["invaders"] == {"u1": {"status": 1}}
        assert bot_empires.find_save(12345) is None


def test_wins_count_for_the_day(monkeypatch, tmp_path):
    with app.test_request_context():
        user = setup_session(monkeypatch, tmp_path)
        bot_empires.battle_won(bot_empires.FIRST_UID)
        bot_empires.battle_won(12345)  # not a bot
        assert bot_empires.fight_list()["wins"] == 1
        user["userInfo"]["player"]["globalPVPBatch"]["ts"] -= bot_empires.FIGHT_LIST_DURATION
        assert bot_empires.fight_list()["wins"] == 0
