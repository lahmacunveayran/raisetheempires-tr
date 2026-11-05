"""The slot machine checked against the game XML and the client.

The expected prizes come from the file the client reads (assets/29oct2012/gameSettings_with_fixes.xml) through
ElementTree, never through game_settings or slot_machine. How the client takes a prize is from its bytecode
(assets/ZGame.109338.swf, turkce/araclar/abc.py):
- PVPSlotMachinePopup.onSpinResult: handler "addLootToInventory" dispatches ITEM_GIFT with loot.payload and shows
  the icon getImageByName(loot.loot, "icon"), so loot.loot is the item's name; handler "awardResources" dispatches
  RESOURCE_GIFT with loot.payload and shows the resource icon of loot.loot.
- Player.onItemGift: addToInventory(payload.code, parseInt(payload.quantity), or parseInt(payload.yield) without a
  quantity, or 1). Player.onResourceGift: resources.updateResourceAmount(payload.name, payload.yield).
- PVPManager.getFeaturedRewardInfo: the prizes are the <info tier itemName amount> of slotMachineFeatured <set>.
The client never sees how often each prize comes out: that is the server's choice (slot_machine's docstring:
units rare, the grand prize, the last tier, the rarest). DESIGN_WEIGHTS below is that choice written out by the item
type of the XML; the test checks that the server draws with it.
"""
import copy
import functools
import json
import math
import os
import random
import xml.etree.ElementTree as ET

from flask import Flask, session

import slot_machine

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "29oct2012",
                   "gameSettings_with_fixes.xml")
# the server's design (slot_machine docstring), by the <item type> of the XML; the grand prize gets GRAND_WEIGHT
DESIGN_WEIGHTS = {"Buildable": 4, "consumable": 12, "buildablepart": 12, "resource": 15}
GRAND_WEIGHT = 1


@functools.lru_cache(maxsize=None)
def xml_root():
    return ET.parse(XML).getroot()


@functools.lru_cache(maxsize=None)
def featured():
    """[(tier, item name, item code, item type, amount)] of the first slotMachineFeatured set, by tier."""
    root = xml_root()
    items = {item.get("name"): item for item in root.find("items").iter("item")}
    infos = sorted(root.find("slotMachineFeatured").find("set").findall("info"), key=lambda i: int(i.get("tier")))
    return [(int(i.get("tier")), i.get("itemName"), items[i.get("itemName")].get("code"),
             items[i.get("itemName")].get("type"), int(i.get("amount"))) for i in infos]


def prize_key(name, code, item_type):
    """What the prize gives: a resource by its name (item type "resource", the item is named like the resource),
    otherwise the item by its code."""
    return name if item_type == "resource" else code


def expected_weights():
    last = featured()[-1][0]
    return {prize_key(name, code, t): GRAND_WEIGHT if tier == last else DESIGN_WEIGHTS[t]
            for tier, name, code, t, _ in featured()}


def game_cost(name, variant=0):  # <gamesettings name="v0,v1,..."> by the empire_globalpvp_slotpull_epcost variant
    return int(xml_root().find("gamesettings").get(name).split(",")[variant])


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
    """random.choices picks the prize that names key (a resource or an item code); the rest stays the server's."""
    def choices(population, weights=None, k=1):
        [chosen] = [p for p in population if p[0] == key]
        return [chosen]
    monkeypatch.setattr(slot_machine.random, "choices", choices)


def binomial_bounds(n, p, alpha):
    """[lo, hi] with P(X < lo) <= alpha / 2 and P(X > hi) <= alpha / 2 for X ~ Binomial(n, p), exactly."""
    log_pmf = [math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) +
               (n - k) * math.log(1 - p) for k in range(n + 1)]
    pmf = [math.exp(x) for x in log_pmf]
    below, lo = 0.0, 0
    while below + pmf[lo] <= alpha / 2:
        below += pmf[lo]
        lo += 1
    above, hi = 0.0, n
    while above + pmf[hi] <= alpha / 2:
        above += pmf[hi]
        hi -= 1
    return lo, hi


def test_prizes_come_from_the_featured_set():
    """The 15 prizes of slotMachineFeatured, each with its amount, the last tier (the grand prize) the rarest."""
    with app.test_request_context():
        setup_session()
        loot = slot_machine.prizes()
        weights = expected_weights()
        assert sorted((code, amount, weight) for code, amount, weight in loot) == sorted(
            (prize_key(name, code, t), amount, weights[prize_key(name, code, t)])
            for _, name, code, t, amount in featured())
        assert len(loot) == len(featured()) == 15
        tier, name, code, t, _ = featured()[-1]
        assert weights[prize_key(name, code, t)] < min(w for k, w in weights.items() if k != code)
        units = [prize_key(n, c, t) for _, n, c, t, _ in featured()[:-1] if t == "Buildable"]
        assert units and max(weights[u] for u in units) < min(weights[k] for k in weights if k not in units + [code])


def test_each_prize_reaches_the_save_as_the_client_takes_it(monkeypatch):
    """For every tier: the spin is pinned to that prize, the save changes by the XML amount of the XML item (or
    resource), the response names it the way the client reads it, and the client's own bookkeeping of the response
    ends where the save does."""
    with app.test_request_context():
        for tier, name, code, item_type, amount in featured():
            user = setup_session(tokens=5)
            key = prize_key(name, code, item_type)
            pin_choice(monkeypatch, key)
            before_items, before_res = dict(items(user)), dict(resources(user))

            loot = slot_machine.spin_response(slot_machine.MODE_KEYS)["data"]["loot"]

            expected_items, expected_res = dict(before_items), dict(before_res)
            expected_items["GPTK"] = 5 - game_cost("GlobalPVPSlotPullKeyCost")
            if item_type == "resource":
                expected_res[name] += amount
                assert loot["handler"] == "awardResources" and loot["loot"] == name
            else:
                expected_items[code] = expected_items.get(code, 0) + amount
                assert loot["handler"] == "addLootToInventory" and loot["loot"] == name  # the icon by item name
            assert (items(user), resources(user)) == (expected_items, expected_res), tier
            client_items, client_res = client_applies(loot, before_items, before_res)
            client_items["GPTK"] = expected_items["GPTK"]  # the client takes the tokens itself
            assert (client_items, client_res) == (expected_items, expected_res), tier


N_SPINS = 10_000
FALSE_ALARM = 1e-6  # for the whole test: each of the 15 prizes gets FALSE_ALARM / 15


def test_prizes_come_out_by_their_weights(monkeypatch):
    """10 000 spins with a fixed seed. If the server draws with the design weights, the count of each prize is
    Binomial(10 000, weight / total); the bounds hold with probability 1 - 1e-6 for any seed (exact binomial
    tails, split over the prizes), so a failure means the draw is not by these weights."""
    rng = random.Random(20121029)
    monkeypatch.setattr(slot_machine.random, "choices", rng.choices)
    weights = expected_weights()
    total = sum(weights.values())
    counts = dict.fromkeys(weights, 0)
    with app.test_request_context():
        setup_session()
        for _ in range(N_SPINS):
            session["user_object"]["userInfo"]["player"]["cash"] = 100
            loot = slot_machine.spin_response(slot_machine.MODE_BUY)["data"]["loot"]
            key = loot["payload"]["name"] if loot["handler"] == "awardResources" else loot["payload"]["code"]
            counts[key] += 1  # a prize outside the XML table is a KeyError
    assert set(counts) == set(weights)
    for key, weight in weights.items():
        lo, hi = binomial_bounds(N_SPINS, weight / total, FALSE_ALARM / len(weights))
        assert lo <= counts[key] <= hi, (key, counts[key], lo, hi)


def test_spin_with_cash():
    with app.test_request_context():
        user = setup_session()
        slot_machine.spin_response(slot_machine.MODE_BUY)
        assert user["userInfo"]["player"]["cash"] == 100 - game_cost("GlobalPVPSlotPullEPCost")  # variant 0
        user["experiments"]["empire_globalpvp_slotpull_epcost"] = 3
        slot_machine.spin_response(slot_machine.MODE_BUY)
        assert user["userInfo"]["player"]["cash"] == 100 - game_cost("GlobalPVPSlotPullEPCost") - \
            game_cost("GlobalPVPSlotPullEPCost", 3)


def test_login_turns_on_the_strangers_bar():
    with app.test_request_context():
        user = setup_session()
        user["experiments"]["empire_globalpvp_strangerbar_enable"] = 0
        slot_machine.update_slot_machine(user)
        assert user["experiments"]["empire_globalpvp_strangerbar_enable"] == 2
        assert user["experiments"]["empire_globalpvp_master"] == 2
        assert user["globalPVPOptIn"] is True
        slot_machine.opt_in_response(False)
        slot_machine.update_slot_machine(user)
        assert user["globalPVPOptIn"] is False  # opting out is kept
