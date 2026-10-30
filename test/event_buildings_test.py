import copy
import datetime
import json
import os

import pytest
from flask import Flask, session

import event_buildings
import quest_engine
import quest_trees
import state_machine
from quest_engine import lookup_quest, get_tasks

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

SHIP = next(name for name, item in quest_trees.ITEMS_BY_NAME.items()
            if "W" in str(item.get("canBuildOn", "")) and int(item.get("sizeX", 1)) == 1)
ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "29oct2012")
DAY = datetime.date(2026, 10, 30)
VOLCANO, METEORITE = event_buildings.BY_KEY["volcanoPower"], event_buildings.BY_KEY["meteoriteMining"]


@pytest.fixture(autouse=True)
def state_file(monkeypatch, tmp_path):
    monkeypatch.setattr(event_buildings, "_state_file", lambda: str(tmp_path / "event_buildings.json"))
    set_today(monkeypatch, DAY)


def set_today(monkeypatch, day):
    monkeypatch.setattr(event_buildings, "_today", lambda: day)


def setup_session(level=40):
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    user["userInfo"]["player"]["inventory"] = {"items": {}}
    user["userInfo"]["world"] = {"sizeX": 60, "sizeY": 60, "globalObjectId": 100, "roadData": [],
                                 "resources": {"coins": 0, "energy": 0, "oil": 0, "wood": 0, "aluminum": 0,
                                               "copper": 0, "gold": 0, "iron": 0, "uranium": 0},
                                 "resourceOrder": ["aluminum", "copper", "gold", "iron", "uranium"], "research": {},
                                 "rewardRandSeedZ": 0, "rewardRandSeedW": 0,
                                 "objects": [{"id": i, "itemName": SHIP, "position": "%d,30,0" % (20 + i), "state": "0"}
                                             for i in range(20)]}
    user["experiments"] = {}
    session["user_object"] = user
    session["quests"] = []
    return user


def login():
    """What the client does on a page load: fetch the settings, then initUser."""
    event_buildings.served_event()
    user = session["user_object"]
    new_quests, meta = [], {}
    event_buildings.update_event_buildings(user, new_quests, meta)
    session["quests"][:] = new_quests + session["quests"]
    return user, new_quests


def building(user, event):
    return event_buildings._buildings(user["userInfo"]["world"], event)


def items(user):
    return user["userInfo"]["player"]["inventory"]["items"]


def quest(name):
    return next(q for q in session["quests"] if q["name"] == name)


def test_events_match_their_items_and_quests():
    for event in event_buildings.EVENTS:
        parts = event_buildings.parts(event)
        assert len(parts) == 6 and all(count > 0 for _, count in parts)
        inventory_task, state_task = get_tasks(lookup_quest(event["quest"]))
        assert inventory_task["_item"] == ",".join(code for code, _ in parts)
        assert int(inventory_task["_total"]) == sum(count for _, count in parts)
        assert state_task["_item"] == event["code"] and state_task["_state"] == event_buildings.ACTIVATED
        assert event["tiers"][-1][0] == event["days"]


def test_first_login_announces_the_event_and_the_next_one_starts_it():
    with app.test_request_context():
        user = setup_session()
        new_quests, meta = [], {}
        event_buildings.update_event_buildings(user, new_quests, meta)
        assert user["experiments"]["empire_volcano_power_master"] == 3
        assert user["userInfo"]["player"]["eventBuildings"]["event"] == "volcanoPower"
        assert not building(user, VOLCANO) and not new_quests  # the settings served this time lack the dates

        user, new_quests = login()

        [placed] = building(user, VOLCANO)
        assert placed["state"] == event_buildings.CONSTRUCTED
        assert [q["name"] for q in new_quests] == ["QVP"]
        assert items(user) == {"B785": 4}  # the part of the first day
        assert quest("QVP")["progress"] == [4, 0]
        assert user["userInfo"]["player"]["eventBuildings"]["start"] == DAY.isoformat()


def test_one_part_a_day(monkeypatch):
    with app.test_request_context():
        user = setup_session()
        login()
        login()
        login()
        assert items(user) == {"B785": 4}
        set_today(monkeypatch, DAY + datetime.timedelta(days=1))
        login()
        assert items(user) == {"B785": 4, "B786": 4}
        assert quest("QVP")["progress"] == [8, 0]
        set_today(monkeypatch, DAY + datetime.timedelta(days=7))  # the parts come round again
        items(user)["B786"] = 1
        login()
        assert items(user)["B786"] == 4


def test_event_quests_are_not_unlocked_by_level():
    with app.test_request_context():
        user = setup_session()
        user["experiments"]["empire_volcano_power_master"] = 3
        user["experiments"]["empire_meteoritemining_master"] = 3
        assert not quest_engine.matches_requirement(lookup_quest("QVP"))
        assert not quest_engine.matches_requirement(lookup_quest("QBB29_01"))


def test_no_event_below_level_15():
    with app.test_request_context():
        user = setup_session(level=10)
        login()
        login()
        assert not building(user, VOLCANO) and not session["quests"]


def activate(user, event):
    [placed] = building(user, event)
    meta = {}
    state_machine.click_next_state(True, placed["id"], meta, "setState", None, cancel=None)
    event_buildings.after_state_change(placed, meta)
    return meta


def test_activating_completes_the_quest_with_the_reward_of_the_day(monkeypatch):
    with app.test_request_context():
        user = setup_session()
        login()
        login()
        set_today(monkeypatch, DAY + datetime.timedelta(days=16))  # second tier of the volcano
        items(user).update({code: count for code, count in event_buildings.parts(VOLCANO)})

        activate(user, VOLCANO)

        assert quest("QVP")["complete"]
        assert items(user) == {"EN8": 2}  # parts used up
        assert not building(user, VOLCANO)
        assert user["userInfo"]["player"]["eventBuildings"]["event"] == "meteoriteMining"

        user, new_quests = login()  # the meteorite event starts on this day
        assert [q["name"] for q in new_quests] == ["QBB29"] and building(user, METEORITE)


def test_activating_with_parts_lost_on_the_server_still_gives_the_reward():
    with app.test_request_context():
        user = setup_session()
        login()
        login()
        items(user).update({"B786": 1, "B787": 1})  # the client had them all, the server did not

        meta = activate(user, VOLCANO)

        assert quest("QVP")["complete"] and quest("QVP")["progress"] == [24, 1]
        assert [q["name"] for q in meta["QuestComponent"] if q["complete"]] == ["QVP"]
        assert items(user) == {"EN8": 3}
        assert not building(user, VOLCANO)


def test_meteorite_gives_each_ore_and_the_trophy():
    rewards = event_buildings.tier_rewards(METEORITE, DAY, DAY + datetime.timedelta(days=13))
    assert {"_type": "item", "_item": "BB30", "_count": "1"} in rewards
    assert [r["_count"] for r in rewards if r["_type"].startswith("nrare")] == ["300"] * 5
    late = event_buildings.tier_rewards(METEORITE, DAY, DAY + datetime.timedelta(days=40))
    assert [r["_count"] for r in late if r["_type"] == "nrare0"] == ["100"]


def test_collect_only_after_the_end(monkeypatch):
    with app.test_request_context():
        user = setup_session()
        user["userInfo"]["player"]["eventBuildings"] = {"next": 1, "event": None, "start": None}
        login()
        login()
        [placed] = building(user, METEORITE)

        early = event_buildings.collect_response("collectMeteoriteCoins", placed["id"], {})
        assert early["data"] == {"id": placed["id"]} and building(user, METEORITE)

        set_today(monkeypatch, DAY + datetime.timedelta(days=24))
        response = event_buildings.collect_response("collectMeteoriteCoins", placed["id"], {})

        assert response["data"] == {"id": placed["id"], "coins": 1000}
        assert user["userInfo"]["world"]["resources"]["coins"] == 1000
        assert not building(user, METEORITE) and "QBB29" not in [q["name"] for q in session["quests"]]
        assert "B855" not in items(user)
        assert user["userInfo"]["player"]["eventBuildings"]["event"] == "deepSeaDrill"
        again = event_buildings.collect_response("collectMeteoriteCoins", placed["id"], {})
        assert "coins" not in again["data"]


def test_volcano_pays_energy_for_the_parts(monkeypatch):
    with app.test_request_context():
        user = setup_session()
        login()
        login()
        items(user)["B786"] = 2
        [placed] = building(user, VOLCANO)
        set_today(monkeypatch, DAY + datetime.timedelta(days=27))

        response = event_buildings.collect_response("collectEnergy", placed["id"], {})

        assert response["data"]["energy"] == {"EN1": 6}
        assert items(user) == {"EN1": 6}


def running(event):
    return event, DAY


def test_settings_carry_the_dates_and_working_assets():
    with open(os.path.join(ASSETS, "gameSettings_with_fixes.xml"), encoding="utf-8") as f:
        xml = f.read()

    patched = event_buildings.patch_settings_xml(xml, running(METEORITE))

    assert '<meteoriteMining><requiredDate start="10/30/2026" end="11/23/2026"/></meteoriteMining>' in patched
    assert '<volcanoPower><requiredDate start="06/21/2012"' in patched  # not running
    for event in event_buildings.EVENTS:
        start, end = event_buildings._item_block(patched, event["code"])
        assert 'buildingPartsDialog="PotOfOre_PartsGather"' in patched[start:end]
    start, end = event_buildings._item_block(patched, "BB36")
    assert "Buildings_Buildables_03.swf" not in patched[start:end]
    for event in event_buildings.EVENTS:
        for code in [event["code"]] + [p for p, _ in event_buildings.parts(event)]:
            start, end = event_buildings._item_block(patched, code)
            for url in __import__("re").findall(r'url="([^"]*)"', patched[start:end]):
                assert quest_trees._asset_exists(url), (code, url)


def test_quest_settings_carry_the_dates_and_the_rewards_given():
    with open(os.path.join(ASSETS, "questSettings_with_fixes.xml"), encoding="utf-8") as f:
        xml = f.read()

    patched = event_buildings.patch_quest_xml(xml, running(METEORITE))

    begin, end = event_buildings._quest_block(patched, "QBB29")
    block = patched[begin:end]
    assert '<requiredDate start="10/30/2026" end="11/23/2026"/>' in block
    assert 'item="B870"' not in block
    assert '<reward type="item" item="BB30" count="1"/>' in block
    assert '<reward type="nrare4" count="600"><requiredDate start="11/05/2026" end="11/11/2026"/></reward>' in block
    assert len(patched) - len(xml) < 2000  # nothing else touched
    begin, end = event_buildings._quest_block(patched, "QNP")
    assert "NPPL_" not in patched[begin:end]
