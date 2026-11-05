"""Mega series checked against the game XML.

The series, their quests and what the client needs of them come from the file the client reads
(assets/29oct2012/gameSettings_with_fixes.xml) through ElementTree here, never through game_settings or megaseries:
<megaSeriesList><megaSeries id entryPointName rewardQuest><requiredExperiment name variants/><criteria><level min
max/></criteria><stage><node quest/>... The quests of a series are its nodes in file order, stage after stage;
the last one is the series' rewardQuest (the node of type="msreward"). Which series are playable depends on the
assets present (megaseries.PLAYABLE); the order they are offered in is the XML's.
"""
import copy
import functools
import json
import os
import xml.etree.ElementTree as ET

import pytest
from flask import Flask, session

import megaseries
import quest_trees

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "29oct2012",
                   "gameSettings_with_fixes.xml")


@functools.lru_cache(maxsize=None)
def xml_series():
    """{id: <megaSeries>} in file order."""
    return {s.get("id"): s for s in ET.parse(XML).getroot().find("megaSeriesList").findall("megaSeries")}


def xml_quests(series_id):
    return [n.get("quest") for stage in xml_series()[series_id].findall("stage") for n in stage.findall("node")
            if n.get("quest")]


def xml_experiment(series_id):
    e = xml_series()[series_id].find("requiredExperiment")
    return e.get("name"), int(e.get("variants").split(",")[0])


def xml_level_ok(series_id, level):
    criteria = xml_series()[series_id].find("criteria/level")
    return int(criteria.get("min", 0)) <= level <= int(criteria.get("max", 9999))


def first_offered(level, skip=()):
    """The first playable series in XML order the player's level allows."""
    return next(s for s in xml_series() if s in megaseries.PLAYABLE and s not in skip and xml_level_ok(s, level))


SHIP = next(name for name, item in quest_trees.ITEMS_BY_NAME.items()
            if "W" in str(item.get("canBuildOn", "")) and int(item.get("sizeX", 1)) == 1)


@pytest.fixture(autouse=True)
def spots_file(monkeypatch, tmp_path):
    monkeypatch.setattr(quest_trees, "_spots_file", lambda: str(tmp_path / "quest_tree_spots.json"))


def setup_session(level=40, with_water=True):
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    user["userInfo"]["world"] = {"sizeX": 60, "sizeY": 60, "globalObjectId": 100, "roadData": [], "resourceOrder": [],
                                 "objects": [{"id": i, "itemName": SHIP, "position": "%d,30,0" % (20 + i), "state": "0"}
                                             for i in range(20)] if with_water else []}
    session["user_object"] = user
    session["quests"] = []
    return user


def login():
    user = session["user_object"]
    new_quests, meta = [], {}
    megaseries.update_megaseries(user, new_quests, meta)
    session["quests"][:] = new_quests + session["quests"]
    return user, new_quests


def test_playable_series_have_quests_and_entry_buildings():
    """Every series reads as the XML has it: its quests stage after stage, ending with the reward quest, and its
    entry building."""
    assert set(megaseries.SERIES) == set(xml_series())
    assert len(megaseries.PLAYABLE) >= 2  # the next tests offer two series one after the other
    for series_id in megaseries.SERIES:
        quests = xml_quests(series_id)
        assert megaseries.nodes(megaseries.SERIES[series_id]) == quests
        assert quests[-1] == xml_series()[series_id].get("rewardQuest")
    for series_id in megaseries.PLAYABLE:
        assert megaseries.entry_item(megaseries.SERIES[series_id])["-name"] == \
            xml_series()[series_id].get("entryPointName")


def test_login_offers_a_series_with_building_experiment_and_first_quest():
    with app.test_request_context():
        setup_session()
        user, new_quests = login()
        player = user["userInfo"]["player"]

        series_id = first_offered(40)
        assert player["megaseriesList"] == {series_id: xml_quests(series_id)[0]}
        assert [q["name"] for q in new_quests] == [xml_quests(series_id)[0]]
        name, variant = xml_experiment(series_id)
        assert user["experiments"][name] == variant
        entry_name = xml_series()[series_id].get("entryPointName")
        entry = [o for o in user["userInfo"]["world"]["objects"] if o["itemName"] == entry_name]
        assert len(entry) == 1 and entry[0]["state"] == "0" and entry[0]["id"] == 101  # globalObjectId 100 + 1

        login()  # nothing new while the series is not finished
        assert list(player["megaseriesList"]) == [series_id]
        assert len([o for o in user["userInfo"]["world"]["objects"] if o["itemName"] == entry_name]) == 1


def test_no_series_without_water_or_below_level():
    with app.test_request_context():
        setup_session(with_water=False)
        user, _ = login()
        assert user["userInfo"]["player"]["megaseriesList"] == {}
        lowest = min(int(xml_series()[s].find("criteria/level").get("min")) for s in megaseries.PLAYABLE)
        setup_session(level=lowest - 1)
        user, _ = login()
        assert user["userInfo"]["player"]["megaseriesList"] == {}
        setup_session(level=lowest)
        user, _ = login()
        assert list(user["userInfo"]["player"]["megaseriesList"]) == [first_offered(lowest)]


def test_finished_series_keeps_its_key_and_makes_room_for_the_next():
    with app.test_request_context():
        user = setup_session()
        login()
        player = user["userInfo"]["player"]
        first = first_offered(40)
        session["quests"][:] = [{"name": q, "complete": True, "expired": False, "progress": [], "completedTasks": 0}
                                for q in xml_quests(first)]

        login()

        second = first_offered(40, skip=[first])
        assert player["megaseriesList"] == {first: xml_series()[first].get("rewardQuest"),
                                            second: xml_quests(second)[0]}
        assert player["megaseriesFinished"] == [first]


def test_reset_starts_the_series_again():
    with app.test_request_context():
        user = setup_session()
        login()
        series_id = first_offered(40)
        quests = xml_quests(series_id)
        session["quests"][:] = [{"name": q, "complete": True, "expired": False, "progress": [], "completedTasks": 0}
                                for q in quests[:3]]

        megaseries.reset_response([series_id])

        assert [q["name"] for q in session["quests"]] == [quests[0]]
        assert session["quests"][0]["complete"] is False
        assert user["userInfo"]["player"]["megaseriesList"][series_id] == quests[0]
