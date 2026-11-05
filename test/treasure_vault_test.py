"""The Treasure Vault checked against the game XML and the client.

What each vault held was decided by Zynga's server and is lost (treasure_vault's docstring): the tables
treasure_vault.LOOT are this server's design, so here they are the input. What the test checks against them comes
from elsewhere:
- assets/29oct2012/gameSettings_with_fixes.xml read with ElementTree: the costs (treasureVaultCosts), the items of
  the prizes and the claim that the tables are made of the slot machine's prizes (slotMachineFeatured);
- the client's bytecode (assets/ZGame.109338.swf, turkce/araclar/abc.py): TreasureVaultRewardPopup
  .populateUIWithSpinResults shows loot.handler "addLootToInventory" with the icon of loot.loot and the item of
  payload.code, "awardResources" with payload.name and "x" + payload.yield; the client books the prize itself with
  Player.onItemGift (addToInventory(payload.code, parseInt(payload.quantity) or else parseInt(payload.yield)))
  and Player.onResourceGift (updateResourceAmount(payload.name, payload.yield)).
The draw is pinned (random.choices) to each prize in turn; the weights are checked by counting with a fixed seed
against exact binomial bounds.
"""
import copy
import functools
import json
import math
import os
import random
import xml.etree.ElementTree as ET

from flask import Flask, session

import quest_engine
import treasure_vault
from quest_engine import lookup_quest

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "29oct2012",
                   "gameSettings_with_fixes.xml")
NOW = 1_800_000_000


@functools.lru_cache(maxsize=None)
def xml_root():
    return ET.parse(XML).getroot()


@functools.lru_cache(maxsize=None)
def xml_items():
    """{code: <item>} and {name: <item>}; a few items are in the file twice, these are not among them."""
    found = list(xml_root().find("items").iter("item"))
    return {i.get("code"): i for i in found}, {i.get("name"): i for i in found}


def xml_cost(tier, variant=0):
    """(keys, cash) of <treasureVaultCosts><variant index><info tier keys cash>."""
    [v] = [v for v in xml_root().find("treasureVaultCosts").findall("variant") if int(v.get("index")) == variant]
    [info] = [i for i in v.findall("info") if int(i.get("tier")) == tier]
    return int(info.get("keys")), int(info.get("cash"))


def featured_prizes():
    """The slot machine's prizes (slotMachineFeatured): resources by name (item type "resource"), items by code."""
    _, by_name = xml_items()
    out = set()
    for info in xml_root().find("slotMachineFeatured").find("set").findall("info"):
        item = by_name[info.get("itemName")]
        out.add(item.get("name") if item.get("type") == "resource" else item.get("code"))
    return out


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


def resources(user):
    return user["userInfo"]["world"]["resources"]


def client_applies(loot, inventory, world_resources):
    """What the client does with the prize of the response (Player.onItemGift / onResourceGift)."""
    inventory, world_resources = dict(inventory), dict(world_resources)
    payload = loot["payload"]
    if loot["handler"] == "addLootToInventory":
        amount = int(payload["quantity"]) if "quantity" in payload else int(payload["yield"]) if "yield" in payload \
            else 1
        inventory[payload["code"]] = inventory.get(payload["code"], 0) + amount
    elif loot["handler"] == "awardResources":
        world_resources[payload["name"]] = world_resources.get(payload["name"], 0) + payload["yield"]
    return inventory, world_resources


def pin_choice(monkeypatch, key):
    """random.choices picks the prize that names key (a resource or an item code)."""
    def choices(population, weights=None, k=1):
        [chosen] = [p for p in population if p[0] == key]
        return [chosen]
    monkeypatch.setattr(treasure_vault.random, "choices", choices)


def binomial_bounds(n, p, alpha):
    """[lo, hi] with P(X < lo) <= alpha / 2 and P(X > hi) <= alpha / 2 for X ~ Binomial(n, p), exactly."""
    pmf = [math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) +
                    (n - k) * math.log(1 - p)) for k in range(n + 1)]
    below, lo = 0.0, 0
    while below + pmf[lo] <= alpha / 2:
        below += pmf[lo]
        lo += 1
    above, hi = 0.0, n
    while above + pmf[hi] <= alpha / 2:
        above += pmf[hi]
        hi -= 1
    return lo, hi


def test_every_prize_exists_and_fits_the_window():
    """Every prize is an item of the XML or a resource, the vaults' prizes are the slot machine's (the docstring's
    claim), the window has 8 places, and the highlights name each item as the client shows it (its XML name)."""
    by_code, _ = xml_items()
    with app.test_request_context():
        all_prizes = set()
        for tier, loot in treasure_vault.LOOT.items():
            assert len(loot) <= 8  # the window has 8 places
            for code, amount, weight in loot:
                assert code in ("coins", "oil", "wood") or code in by_code
                assert amount >= 1 and weight >= 1
                all_prizes.add(code)
        assert all_prizes == featured_prizes()
        highlights = treasure_vault.highlights()
        assert sorted(highlights) == ["treasure_vault_tier_%d" % t for t in range(1, 5)]
        for tier, loot in treasure_vault.LOOT.items():
            shown = highlights["treasure_vault_tier_%d" % tier]["lootItem"]
            assert [(e["payload"].get("code") or e["payload"]["name"]) for e in shown] == [c for c, _, _ in loot]
            for entry, (code, amount, _) in zip(shown, loot):
                if code in by_code:
                    assert entry["loot"] == entry["itemName"] == by_code[code].get("name")
                    assert entry["payload"]["quantity"] == amount
                else:
                    assert entry["loot"] == code and entry["payload"]["yield"] == amount


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


def test_each_prize_reaches_the_save_as_the_client_takes_it(monkeypatch):
    """Every prize of every vault, the draw pinned to it, opened with keys: the keys of the XML cost are taken, the
    save gets the prize, the response names it as the client reads it, and the client's own bookkeeping of the
    response ends where the save does."""
    by_code, _ = xml_items()
    with app.test_request_context():
        for tier, loot in treasure_vault.LOOT.items():
            keys, _ = xml_cost(tier)
            for code, amount, _ in loot:
                user = setup_session(monkeypatch, keys=keys + 1)
                pin_choice(monkeypatch, code)
                before_items, before_res = dict(items(user)), dict(resources(user))

                response = treasure_vault.spin_response(treasure_vault.MODE_KEYS, tier)
                loot_entry = response["data"]["loot"]

                expected_items, expected_res = dict(before_items), dict(before_res)
                expected_items["B265"] = 1
                if code in by_code:
                    expected_items[code] = expected_items.get(code, 0) + amount
                    assert loot_entry["handler"] == "addLootToInventory"
                    assert loot_entry["loot"] == by_code[code].get("name")  # the icon by the item's name
                else:
                    expected_res[code] += amount
                    assert loot_entry["handler"] == "awardResources" and loot_entry["loot"] == code
                assert (items(user), resources(user)) == (expected_items, expected_res), (tier, code)
                assert user["userInfo"]["player"]["treasureVaultOpenTS"] == NOW
                client_items, client_res = client_applies(loot_entry, before_items, before_res)
                client_items["B265"] = 1  # the client takes the keys itself
                assert (client_items, client_res) == (expected_items, expected_res), (tier, code)


def test_open_with_cash(monkeypatch):
    with app.test_request_context():
        for tier in treasure_vault.LOOT:
            user = setup_session(monkeypatch)
            treasure_vault.spin_response(treasure_vault.MODE_BUY, tier)
            assert user["userInfo"]["player"]["cash"] == 100 - xml_cost(tier)[1]
            assert user["userInfo"]["player"]["treasureVaultOpenTS"] == 0  # buying does not start the key timer
        user = setup_session(monkeypatch)
        user["experiments"]["empire_vault_tierprice"] = 3
        treasure_vault.spin_response(treasure_vault.MODE_BUY, 4)
        assert user["userInfo"]["player"]["cash"] == 100 - xml_cost(4, 3)[1]


N_SPINS = 5_000  # a vault
FALSE_ALARM = 1e-6  # for the whole test, split evenly over all prizes of all vaults


def test_every_vault_gives_its_prizes_by_their_weights(monkeypatch):
    """5 000 openings of each vault with a fixed seed. If the server draws with the table's weights, the count of
    each prize is Binomial(5 000, weight / total of the vault); the bounds hold with probability 1 - 1e-6 for any
    seed (exact binomial tails), so a failure means the draw is not by the table. Every prize comes out, items and
    resources each by its own name."""
    rng = random.Random(20121029)
    monkeypatch.setattr(treasure_vault.random, "choices", rng.choices)
    prizes = sum(len(loot) for loot in treasure_vault.LOOT.values())
    with app.test_request_context():
        setup_session(monkeypatch)
        for tier, loot in treasure_vault.LOOT.items():
            counts = {code: 0 for code, _, _ in loot}
            for _ in range(N_SPINS):
                session["user_object"]["userInfo"]["player"]["cash"] = 100
                entry = treasure_vault.spin_response(treasure_vault.MODE_BUY, tier)["data"]["loot"]
                counts[entry["payload"].get("code") or entry["payload"]["name"]] += 1  # outside the table: KeyError
            seen = {code for code, n in counts.items() if n}
            assert {code for code, _, _ in loot} <= seen
            total = sum(weight for _, _, weight in loot)
            for code, _, weight in loot:
                lo, hi = binomial_bounds(N_SPINS, weight / total, FALSE_ALARM / prizes)
                assert lo <= counts[code] <= hi, (tier, code, counts[code], lo, hi)
