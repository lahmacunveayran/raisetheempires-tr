"""save_migration.migrate, one step at a time: a small save of the version before the step, and what the step must
make of it, written out here.

Where the expected values come from:
- the experiment variants the client switches the features on with: ExperimentsManager / ZGlobal / SurvivalModeManager
  constants in assets/ZGame.109338.swf and how the client compares them (read with turkce/araclar/abc.py, see
  CLIENT_*);
- experiments the client never reads (or reads without a fixed value): only the server knows them, so a migrated save
  must get what a new save gets (empires-server.py init_user), see NEW_SAVE_*;
- expansions: the 0.03a step gives the expansions a new player starts with (init_user), decoded with the client's
  bit layout (game_settings.unlock_expansion: word index >> 5, bit index & 31);
- the rest from the step's comment in save_migration.py, quoted next to the assert.
"""
import copy
import functools
import itertools
import json
import os
import xml.etree.ElementTree as ET

import pytest
from flask import Flask, session

empires_server = __import__('empires-server')
import save_engine
import save_migration

app = Flask(__name__)
app.secret_key = "test"

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)
QUESTS_XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "29oct2012",
                          "questSettings_with_fixes.xml")
SAVE_IDS = itertools.count()
TARGET = "0.08a.2026_08_13"  # a version after 0.08a, as the server's

# 0.06a features: (variant, where the client reads it)
CLIENT_06 = {
    "empire_decorations_master": 2,  # DecorationsManager.enabled: getExperimentVariant(...) == 2
    "empire_research_shield_upgrade": 2,  # VARIANT_RESEARCH_SHIELD_UPGRADE_ON = 2; BattleUnit.init: equals
}
# empires_support_units: ZGlobal.EXPERIMENT_SUPPORT_UNITS_ACTIVE = 3, PlayerStatsUIItem.onGameInitComplete: ifnge,
# so at least 3; empire_doober_pickup is compared with RewardPickup's own USE_HOOBERS; empires_consumable_2 and
# empire_buildable_zrig_master are not in the client at all
NEW_SAVE_06 = ("empires_support_units", "empire_doober_pickup", "empires_consumable_2", "empire_buildable_zrig_master")
# 0.08a features
CLIENT_08 = {
    "empire_request2_master": 2,  # VARIANT_VALUE_REQUEST2_MASTER_ON = 2; ViralsManager.onTimeout: ifne (== only)
    "empire_survivalmode3_master": 3,  # SurvivalModeManager.VARIANT_SURVIVALMODE3_MASTER_ENABLED = 3; equals
    "empire_survivalMode_master": 2,  # VARIANT_SURVIVALMODE_MASTER = 2; SurvivalModeManager.enabled: ifeq
    "empire_survivalmode_enhancements": 2,  # VARIANT_SURVIVALMODE_ENHANCEMENTS_ENABLED = 2; launchSurvivalMode: ifne
    "empire_mech_fight_master": 3,  # VARIANT_TITAN_FIGHT_ACTIVE = 3; MechBattleSetup.isEnabled: ifne (== only)
    "empire_mech_lab_master": 3,  # VARIANT_VALUE_MECH_LAB_ENABLED = 3; MechLabPartsDialogState.showDialog: ifnge
    "empire_campv2_enabled": 2,  # EXPERIMENT_CAMPV2_ENABLED_VARIANT_ENABLED = 2; PlayerCampaign.currentCampaignName
    "empire_campaign_mastery": 2,  # ZGlobal.EXPERIMENT_CAMPAIGN_MASTERY_ENABLED = 2; BattleSelectPopup.<init>: ifne
}
# empire_mfs_uili: RequestDialog.<init> keeps the variant, no fixed value; empire_mech_fight_gate_flat and
# empire_titanresearch_master are not in the client; empire_tier_8: EXPERIMENT_TIER_8_VARIANT_ENABLE = 3 is defined
# but never read
NEW_SAVE_08 = ("empire_mfs_uili", "empire_mech_fight_gate_flat", "empire_titanresearch_master", "empire_tier_8")


@functools.lru_cache(maxsize=None)
def new_save_experiments():
    with app.test_request_context():
        session.sid = "0"
        original = empires_server.get_saves
        empires_server.get_saves = lambda: []
        try:
            return copy.deepcopy(empires_server.init_user()["experiments"])
        finally:
            empires_server.get_saves = original


@functools.lru_cache(maxsize=None)
def new_save_expansions():
    with app.test_request_context():
        session.sid = "0"
        original = empires_server.get_saves
        empires_server.get_saves = lambda: []
        try:
            return list(empires_server.init_user()["userInfo"]["player"]["expansions"]["data"])
        finally:
            empires_server.get_saves = original


def unlocked(words):
    """The expansion numbers whose bit is set (game_settings.unlock_expansion: word index >> 5, bit index & 31)."""
    return {32 * i + bit for i, word in enumerate(words) for bit in range(32) if word >> bit & 1}


@functools.lru_cache(maxsize=None)
def open_quest_with_a_long_task():
    """A quest of one task that takes more than one step (not population, which counts the population instead)."""
    for quest in ET.parse(QUESTS_XML).getroot().iter("quest"):
        tasks = quest.find("tasks")
        if tasks is not None and len(tasks) == 1 and int(tasks[0].get("total", 0)) >= 3 and \
                tasks[0].get("action") not in ("population", "countPlaced", "autoComplete"):
            return quest.get("name")


def old_save(version, objects=(), experiments=None):
    user_object = copy.deepcopy(INIT_USER)
    user_object["experiments"] = dict(experiments or {})
    user_object["userInfo"]["world"]["objects"] = [dict(o) for o in objects]
    session.clear()
    session.update(user_object=user_object, quests=[], save_version=version, saved_on=1_600_000_000.0)
    session.sid = "save%d" % next(SAVE_IDS)  # its own backups
    return copy.deepcopy(dict(session))


def backup_messages():
    return [(info["message"], info["save_version"]) for _, info in save_engine.list_backups(session)]


def test_0_02a_resets_the_open_quests_and_the_expansions():
    """"quests and expansions are reset below": the open quests lose their completed tasks and are counted again
    without adding anything (yield 0); done quests stay done; the expansions are those of a new player."""
    name = open_quest_with_a_long_task()
    with app.test_request_context():
        old_save("0.02a")
        session["quests"] = [{"name": name, "complete": False, "expired": False, "progress": [1],
                              "completedTasks": 1},
                             {"name": "Q0516", "complete": True, "expired": False, "progress": [1],
                              "completedTasks": 1}]
        session["user_object"]["userInfo"]["player"]["expansions"]["data"] = [0xFFFFFFFF] * 23

        save_migration.migrate({}, "0.02a", "0.03a")

        assert session["quests"] == [{"name": name, "complete": False, "expired": False, "progress": [1],
                                      "completedTasks": 0},
                                     {"name": "Q0516", "complete": True, "expired": False, "progress": [1],
                                      "completedTasks": 1}]
        assert unlocked(session["user_object"]["userInfo"]["player"]["expansions"]["data"]) == \
            unlocked(new_save_expansions())
        assert session["save_version"] == "0.03a"
        assert backup_messages() == [("Update to 0.03a", "0.02a")]


@pytest.mark.parametrize("version,step,message", [("0.03a", "0.04a", "Update to 0.04a"),
                                                  ("0.04a", "0.05a", "Update to 0.05a"),
                                                  ("0.06a", "0.07a", "Update to 0.07a")])
def test_steps_that_only_change_the_version(version, step, message):
    with app.test_request_context():
        before = old_save(version, objects=[{"id": 1, "itemName": "Parliament", "state": "8"}])

        save_migration.migrate({}, version, step)

        assert dict(session) == dict(before, save_version=step, saved_on=session["saved_on"])
        assert backup_messages() == [(message, version)]


def test_0_05a_staffs_the_built_government_buildings():
    """govt_fixer: a built (state 8 and up) government building without crew gets its crew places, empty (-1).
    How many each building has is only in govt_fixer's own table (Parliament 3, Prison 8, Space Agency 12); the
    client's crew template of the building (gameSettings <crewTemplate>) must have room for them."""
    objects = [{"id": 1, "itemName": "Parliament", "state": "8"}, {"id": 2, "itemName": "Prison", "state": "9"},
               {"id": 3, "itemName": "Space Agency", "state": 8}, {"id": 4, "itemName": "Treasury", "state": "7"},
               {"id": 5, "itemName": "Mint", "state": "8", "crewInfo": ["123"]},
               {"id": 6, "itemName": "Market", "state": "8"}]
    for version in ("0.05a", "0.05a.2"):  # 0.05a and its patch releases
        with app.test_request_context():
            old_save(version, objects=objects)

            save_migration.migrate({}, version, "0.06a")

            crews = {o["itemName"]: o.get("crewInfo") for o in session["user_object"]["userInfo"]["world"]["objects"]}
            assert crews == {"Parliament": [-1] * 3, "Prison": [-1] * 8, "Space Agency": [-1] * 12, "Treasury": None,
                             "Mint": ["123"], "Market": None}
            assert session["save_version"] == "0.06a"
            assert backup_messages() == [("Update to 0.06a", version)]
    root = ET.parse(os.path.join(os.path.dirname(QUESTS_XML), "gameSettings_with_fixes.xml")).getroot()
    templates = {t.get("crew"): len(t.findall("position")) for t in root.find("crewTemplates")}
    items = {i.get("name"): i.get("crewTemplate") for i in root.iter("item")}
    for building, crew in crews.items():
        if building in ("Parliament", "Prison", "Space Agency"):
            assert len(crew) <= templates[items[building]], building


def test_0_05a_turns_the_0_06a_features_on():
    with app.test_request_context():
        old_save("0.05a", experiments={"empire_decorations_master": 0})

        save_migration.migrate({}, "0.05a", "0.06a")

        experiments = session["user_object"]["experiments"]
        for name, variant in CLIENT_06.items():
            assert experiments[name] == variant, name
        for name in NEW_SAVE_06:
            assert experiments[name] == new_save_experiments()[name], name
        assert experiments["empires_support_units"] >= 3
        assert set(experiments) == set(CLIENT_06) | set(NEW_SAVE_06)


def test_0_07a_turns_the_0_08a_features_on_and_writes_crews_as_text():
    """The 0.08a step: crew places are kept as text (the uids the crew calls write, crew_request_response), the
    0.08a experiments are set, and the save gets the server's version ("version = target_version")."""
    objects = [{"id": 1, "itemName": "Parliament", "state": "8", "crewInfo": [-1, 123, "111"]},
               {"id": 2, "itemName": "Market", "state": "8"}]
    for version in ("0.07a", "0.07a.1"):
        with app.test_request_context():
            old_save(version, objects=objects, experiments={"empire_mech_lab_master": 1})

            save_migration.migrate({}, version, TARGET)

            world = session["user_object"]["userInfo"]["world"]["objects"]
            assert [o.get("crewInfo") for o in world] == [["-1", "123", "111"], None]
            experiments = session["user_object"]["experiments"]
            for name, variant in CLIENT_08.items():
                assert experiments[name] == variant, name
            for name in NEW_SAVE_08:
                assert experiments[name] == new_save_experiments()[name], name
            assert set(experiments) == set(CLIENT_08) | set(NEW_SAVE_08)
            assert session["save_version"] == TARGET
            assert backup_messages() == [("Update to 0.08a full", version)]


def test_a_0_02a_save_goes_through_every_step():
    with app.test_request_context():
        old_save("0.02a", objects=[{"id": 1, "itemName": "Prison", "state": "8"}])

        save_migration.migrate({}, "0.02a", TARGET)

        assert session["save_version"] == TARGET
        assert backup_messages() == [("Update to 0.08a full", "0.07a"), ("Update to 0.07a", "0.06a"),
                                     ("Update to 0.06a", "0.05a"), ("Update to 0.05a", "0.04a"),
                                     ("Update to 0.04a", "0.03a"), ("Update to 0.03a", "0.02a")]
        assert session["user_object"]["userInfo"]["world"]["objects"][0]["crewInfo"] == ["-1"] * 8
        assert session["user_object"]["experiments"] == dict(
            CLIENT_06, **CLIENT_08, **{n: new_save_experiments()[n] for n in NEW_SAVE_06 + NEW_SAVE_08})


def test_a_save_of_the_target_version_is_left_alone():
    for version in ("0.03a", "0.04a", "0.05a", "0.06a", "0.07a"):
        with app.test_request_context():
            before = old_save(version)
            save_migration.migrate({}, version, version)
            assert dict(session) == before, version
            assert backup_messages() == [], version
