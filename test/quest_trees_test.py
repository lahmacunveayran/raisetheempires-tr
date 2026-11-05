"""Mini series (quest trees) checked against the game XML.

The trees and their quests come from the file the client reads (assets/29oct2012/gameSettings_with_fixes.xml)
through ElementTree here, never through game_settings or quest_trees: <questTrees><questTree id rewardQuest
totalQuestTreeAllies><criteria><level min max/></criteria><hook item/><node quest prequel/>... An id that is in the
file twice counts with its last <questTree> (quest_trees keeps the last one, as the client does). The first quest
of a tree is its first node without a prequel. Which trees are playable depends on the assets present
(quest_trees.PLAYABLE); they are offered in the order of the XML.
"""
import copy
import functools
import json
import os
import xml.etree.ElementTree as ET

from flask import Flask, session

import pytest

import quest_trees

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "29oct2012",
                   "gameSettings_with_fixes.xml")
LEVEL = 40


@functools.lru_cache(maxsize=None)
def xml_trees():
    """{id: <questTree>}: in the order an id first appears, the last <questTree> of the id."""
    trees = {}
    for tree in ET.parse(XML).getroot().find("questTrees").findall("questTree"):
        trees[tree.get("id")] = tree
    return trees


def xml_nodes(tree_id):
    return [n.get("quest") for n in xml_trees()[tree_id].findall("node") if n.get("quest")]


def xml_first(tree_id):
    return next(n.get("quest") for n in xml_trees()[tree_id].findall("node") if n.get("quest") and
                not n.get("prequel"))


def xml_level_ok(tree_id, level):
    criteria = xml_trees()[tree_id].find("criteria/level")
    return criteria is None or int(criteria.get("min", 0)) <= level <= int(criteria.get("max", 9999))


def first_offered(level, skip=()):
    """The first playable tree in XML order the player's level allows."""
    return next(t for t in xml_trees() if t in quest_trees.PLAYABLE and t not in skip and xml_level_ok(t, level))


TREE = first_offered(LEVEL)
FIRST = xml_first(TREE)


@pytest.fixture(autouse=True)
def spots_file(monkeypatch, tmp_path):
    monkeypatch.setattr(quest_trees, "_spots_file", lambda: str(tmp_path / "quest_tree_spots.json"))


def setup_session(level=LEVEL):
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    user["neighbors"] = [{"uid": -1}, {"uid": 123}, {"uid": 131}]
    session["user_object"] = user
    session["quests"] = []
    return user


def quest_names():
    return [q["name"] for q in session["quests"]]


def offer_trees():
    user = session["user_object"]
    new_quests, meta = [], {}
    quest_trees.update_quest_trees(user, new_quests, meta)
    session["quests"][:] = new_quests + session["quests"]
    return user["userInfo"]["player"], new_quests


def complete(names):
    for q in session["quests"]:
        if q["name"] in names:
            q["complete"] = True


def test_trees_read_as_the_xml_has_them():
    assert list(quest_trees.TREES) == list(xml_trees())
    for tree_id in xml_trees():
        assert quest_trees.nodes(quest_trees.TREES[tree_id]) == xml_nodes(tree_id)
        # every attribute of every node, so a twice listed id is the last <questTree> (QT011's differ in playerImage)
        assert [{k: v for k, v in n.items() if k.startswith("-")} for n in
                quest_trees._as_list(quest_trees.TREES[tree_id].get("node"))] == \
            [{"-" + k: v for k, v in n.attrib.items()} for n in xml_trees()[tree_id].findall("node")]
        if xml_nodes(tree_id):
            assert quest_trees.first_quest(quest_trees.TREES[tree_id]) == xml_first(tree_id)
    assert len(quest_trees.PLAYABLE) >= 2  # the tests below offer two trees one after the other
    for tree_id in quest_trees.PLAYABLE:
        assert quest_trees.TREES[tree_id]["hook"]["-item"] == xml_trees()[tree_id].find("hook").get("item")


def test_login_offers_one_tree_and_starts_its_first_quest():
    with app.test_request_context():
        setup_session()
        player, new_quests = offer_trees()

        assert player["questTrees"] == {TREE: [FIRST]}
        assert [q["name"] for q in new_quests] == [FIRST]
        # the first totalQuestTreeAllies neighbors (the server's default is 2 when the tree does not say)
        allies = int(xml_trees()[TREE].get("totalQuestTreeAllies", 2))
        assert player["questTreeData"][TREE]["allies"] == [-1, 123, 131][:allies]

        offer_trees()  # logging in again does not offer another tree while this one is unfinished
        assert list(player["questTrees"]) == [TREE]
        assert quest_names().count(FIRST) == 1


def test_low_level_player_gets_no_tree():
    with app.test_request_context():
        lowest = min(int(xml_trees()[t].find("criteria/level").get("min")) for t in quest_trees.PLAYABLE)
        setup_session(level=lowest - 1)
        player, new_quests = offer_trees()

        assert player["questTrees"] == {}
        assert new_quests == []

        setup_session(level=lowest)
        player, _ = offer_trees()
        assert list(player["questTrees"]) == [first_offered(lowest)]


def test_start_quest_tracks_node_and_activates_quest():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = xml_nodes(TREE)[1]

        response = quest_trees.start_quest_response([TREE, second])

        assert player["questTrees"][TREE] == [FIRST, second]
        assert second in quest_names()
        assert [q["name"] for q in response["metadata"]["QuestComponent"]] == [second]
        quest_trees.start_quest_response([TREE, second])  # repeated calls do not duplicate the quest
        assert quest_names().count(second) == 1
        assert player["questTrees"][TREE] == [FIRST, second]


def test_unlock_quest_is_remembered():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = xml_nodes(TREE)[1]

        quest_trees.unlock_quest_response([TREE, second])

        assert player["questTreeUnlocks"][TREE] == [second]


def test_finished_tree_makes_room_for_the_next():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        for name in xml_nodes(TREE):
            quest_trees.start_quest_response([TREE, name])
        complete(xml_nodes(TREE))
        assert not xml_trees()[TREE].get("rewardQuest")  # else the tree stays until its reward quest is done

        offer_trees()

        assert TREE not in player["questTrees"]
        assert player["questTreesFinished"] == [TREE]
        nxt = first_offered(LEVEL, skip=[TREE])
        assert player["questTrees"] == {nxt: [xml_first(nxt)]}


def test_reset_replays_tree():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = xml_nodes(TREE)[1]
        quest_trees.start_quest_response([TREE, second])
        complete([FIRST])

        quest_trees.reset_response([TREE, None])

        assert player["questTreesRestarts"][TREE] == 1
        assert player["questTrees"][TREE] == [FIRST]
        assert second not in quest_names()
        assert [q for q in session["quests"] if q["name"] == FIRST][0]["complete"] is False


def test_reset_single_node():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()
        second = xml_nodes(TREE)[1]
        quest_trees.start_quest_response([TREE, second])

        quest_trees.reset_response([TREE, second])

        assert second not in quest_names()
        assert player["questTrees"][TREE] == [FIRST]


def test_set_mode_stores_mode_and_restarts():
    with app.test_request_context():
        setup_session()
        player, _ = offer_trees()

        quest_trees.set_mode_response([TREE, "hard"])

        assert player["questTreeData"][TREE]["difficultyMode"] == "hard"
        assert player["questTreesRestarts"][TREE] == 1


# Two roads x=5 and x=9, y 5..20, nothing else (no water). By the rule of hook_spots (a free 3x3 spot with at least 6
# land cells in the ring around it, no water within 3, the most surrounded first, then by x and y, spots kept apart
# by a cell): a 3x3 spot fits between the roads only at x=6 (x 6..8); its ring has the cells of both roads for the
# rows y-1..y+3, so 10 land cells for y 6..17, 8 for y 5 and 18, 6 for y 4 and 19, fewer above and below. A spot
# anywhere else touches one road at most, 5 cells. Taken in that order, two spots at y and y' keep apart when
# |y - y'| >= 5: (6,6), then (6,11), then (6,16); all others are too close to one of these.
ROADS_WORLD = {"sizeX": 30, "sizeY": 30, "roadData": ["5,5|5,20", "9,5|9,20"], "objects": []}
ROADS_SPOTS = [(6, 6), (6, 11), (6, 16)]


def test_hook_spots_are_free_land_between_roads():
    assert quest_trees.hook_spots(ROADS_WORLD) == ROADS_SPOTS
    assert quest_trees.hook_spots(ROADS_WORLD, count=2) == ROADS_SPOTS[:2]
    # a single road: the ring of a spot (5 cells high) holds at most 5 of its cells, fewer than 6, so no spot at all
    assert quest_trees.hook_spots({"sizeX": 30, "sizeY": 30, "roadData": ["5,5|5,20"], "objects": []}) == []


def test_hook_spots_are_free_land_next_to_buildings():
    world = {"sizeX": 30, "sizeY": 30, "roadData": ["5,5|5,20", "9,5|9,20"],
             "objects": [{"itemName": "Market", "position": "10,5,0"}, {"itemName": "Market", "position": "10,12,0"}]}
    spots = quest_trees.hook_spots(world)

    assert spots
    taken = {(x, y) for x in (5, 9) for y in range(5, 21)}
    for x, y in spots:
        cells = {(x + i, y + j) for i in range(3) for j in range(3)}
        assert not cells & taken


def test_patch_settings_puts_free_spots_first():
    hook = xml_trees()[TREE].find("hook").get("item")
    xml = '<questTrees><questTree id="%s"><hook item="%s"><pos>1,1</pos></hook></questTree></questTrees>' % (TREE, hook)

    patched = quest_trees.patch_settings_xml(xml, ROADS_SPOTS)

    assert patched == ('<questTrees><questTree id="%s"><hook item="%s"><pos>6,6</pos><pos>6,11</pos><pos>6,16</pos>'
                       '<pos>1,1</pos></hook></questTree></questTrees>' % (TREE, hook))
    assert quest_trees.patch_settings_xml(xml, []) == xml


def test_login_remembers_spots_for_the_next_settings_request():
    with app.test_request_context():
        user = setup_session()
        user["userInfo"]["world"] = copy.deepcopy(ROADS_WORLD)
        offer_trees()

        assert quest_trees.remembered_hook_spots() == ROADS_SPOTS
