import copy
import json
import os

from flask import Flask, session

import quest_engine
import treasure_vault
from quest_engine import lookup_quest

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

NOW = 1_800_000_000


def setup_session(monkeypatch, keys=0, opened=0):
    monkeypatch.setattr(treasure_vault, "_now", lambda: NOW)
    user = copy.deepcopy(INIT_USER)
    player = user["userInfo"]["player"]
    player["cash"] = 100
    player["level"] = 30
    player["treasureVaultOpenTS"] = opened
    player["inventory"] = {"items": {"B265": keys} if keys else {}}
    user["userInfo"]["world"]["resources"] = {"coins": 0, "energy": 0, "oil": 0, "wood": 0, "aluminum": 0,
                                              "copper": 0, "gold": 0, "iron": 0, "uranium": 0}
    user["experiments"] = {}
    session["user_object"] = user
    session["quests"] = []
    return user


def items(user):
    return user["userInfo"]["player"]["inventory"]["items"]


def test_every_prize_exists_and_fits_the_window():
    with app.test_request_context():
        for tier, loot in treasure_vault.LOOT.items():
            assert len(loot) <= 8  # the window has 8 places
            for code, amount, weight in loot:
                assert code in treasure_vault.RESOURCES or treasure_vault._loot_item(code)
        highlights = treasure_vault.highlights()
        assert sorted(highlights) == ["treasure_vault_tier_%d" % t for t in range(1, 5)]
        assert highlights["treasure_vault_tier_4"]["lootItem"][-1]["itemName"] == "Gold Villain Sea 05"


def test_login_opens_the_vault_quest_and_gives_a_free_key(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch)
        treasure_vault.update_treasure_vault(user, [], {})
        assert items(user)["B265"] == 1
        assert user["treasureVaultHighlights"]["treasure_vault_tier_1"]["lootItem"]
        assert quest_engine.matches_requirement(lookup_quest("Q140J"))


def test_players_past_level_26_get_the_vault_quest_once(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch)
        user["userInfo"]["player"]["level"] = 85
        new_quests, meta = [], {}
        treasure_vault.update_treasure_vault(user, new_quests, meta)
        assert [q["name"] for q in new_quests] == ["Q140J", "QB128"]
        assert new_quests[0]["complete"] and not new_quests[1]["complete"]
        assert new_quests[0]["complete"] and items(user)["TV01"] == 1  # the first quest only hands out the vault
        session["quests"][:] = new_quests
        again = []
        treasure_vault.update_treasure_vault(user, again, {})
        assert again == []


def test_no_free_key_within_a_day_or_with_keys_left(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch, opened=NOW - 3600)
        treasure_vault.update_treasure_vault(user, [], {})
        assert "B265" not in items(user)
        user = setup_session(monkeypatch, keys=3)
        treasure_vault.update_treasure_vault(user, [], {})
        assert items(user)["B265"] == 3


def test_open_with_keys(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch, keys=6)
        response = treasure_vault.spin_response(treasure_vault.MODE_KEYS, 2)  # silver: 5 keys
        assert items(user)["B265"] == 1
        assert user["userInfo"]["player"]["treasureVaultOpenTS"] == NOW
        loot = response["data"]["loot"]
        assert loot["handler"] in ("addLootToInventory", "awardResources")
        if loot["handler"] == "addLootToInventory":
            assert items(user)[loot["payload"]["code"]] == loot["payload"]["quantity"]
        else:
            assert user["userInfo"]["world"]["resources"][loot["loot"]] == loot["payload"]["yield"]


def test_open_with_cash(monkeypatch):
    with app.test_request_context():
        user = setup_session(monkeypatch)
        treasure_vault.spin_response(treasure_vault.MODE_BUY, 4)
        assert user["userInfo"]["player"]["cash"] == 100 - 24
        assert user["userInfo"]["player"]["treasureVaultOpenTS"] == 0  # buying does not start the key timer


def test_every_vault_can_give_each_of_its_prizes(monkeypatch):
    with app.test_request_context():
        for tier, loot in treasure_vault.LOOT.items():
            seen = set()
            for _ in range(400):
                setup_session(monkeypatch)
                seen.add(treasure_vault.spin_response(treasure_vault.MODE_BUY, tier)["data"]["loot"]["payload"].get(
                    "code", None) or "res")
            assert len(seen) >= len([1 for code, _, _ in loot if code not in treasure_vault.RESOURCES])
