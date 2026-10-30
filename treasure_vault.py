"""The Treasure Vault (TV01).

A quest gives the vault at level 26; it is built from four parts like other part buildings. Opened, it shows four
vaults (bronze, silver, gold, platinum) paid with vault keys (B265) or cash, see treasureVaultCosts. When the
player runs out of keys a free key comes after 24 hours.

What the vaults held was decided by Zynga's server and is lost: no settings file or archive has it. The tables
below are made from the prizes of the game's own slot machine (slotMachineFeatured), the better ones in the
better vaults. The client shows up to 8 of them per vault (treasureVaultHighlights).
"""
import functools
import random
import time

from flask import session

from game_settings import game_settings
from quest_engine import do_rewards

KEY = "B265"
FREE_KEY_AFTER = 24 * 60 * 60
MODE_BUY, MODE_KEYS = 0, 1
EXPERIMENTS = {"empire_vault_master": 3}  # unlocks the quest that gives the vault

RESOURCES = ("coins", "oil", "wood")
# tier: [(item code or resource, amount, weight)]
LOOT = {
    1: [("coins", 20000, 30), ("wood", 5000, 20), ("oil", 5000, 20), ("EN6", 2, 15), ("B48", 2, 10), ("N36", 1, 5)],
    2: [("coins", 50000, 25), ("EN6", 5, 20), ("B48", 5, 15), ("N36", 2, 15), ("xk01", 1, 10), ("U59", 1, 8),
        ("UL02", 1, 7)],
    3: [("coins", 100000, 20), ("EN6", 10, 15), ("N37", 2, 15), ("xk01", 2, 10), ("U59", 1, 10), ("UL02", 1, 10),
        ("U63", 1, 10), ("UA19", 1, 10)],
    4: [("N37", 3, 20), ("xk01", 3, 15), ("U63", 1, 15), ("UA19", 1, 15), ("UA33", 1, 15), ("US24", 1, 12),
        ("UG15", 1, 8)],
}


def _response(data):
    return {"errorType": 0, "userId": 1, "metadata": {"newPVE": 0}, "data": data}


def _now():
    return time.time()


def _player():
    return session['user_object']["userInfo"]["player"]


def _items():
    return _player()["inventory"]["items"]


def costs(tier):
    """(keys, cash) of a vault for the player's price experiment."""
    variant = int(session['user_object'].get("experiments", {}).get("empire_vault_tierprice", 0) or 0)
    variants = game_settings['settings']['treasureVaultCosts']['variant']
    [costs_variant] = [v for v in variants if int(v["-index"]) == variant] or [variants[0]]
    [info] = [i for i in costs_variant["info"] if int(i["-tier"]) == tier]
    return int(info["-keys"]), int(info["-cash"])


@functools.lru_cache(maxsize=None)
def _loot_item(code):
    from quest_trees import ITEMS_BY_NAME
    return next(item for item in ITEMS_BY_NAME.values() if item.get("-code") == code)


def _entry(code, amount):
    """One prize as the client reads it (handler / loot / payload)."""
    if code in RESOURCES:
        return {"handler": "awardResources", "loot": code, "payload": {"name": code, "yield": amount}}
    name = _loot_item(code)["-name"]
    return {"handler": "addLootToInventory", "loot": name, "itemName": name, "code": code,
            "payload": {"code": code, "quantity": amount, "yield": amount}}


def highlights():
    return {"treasure_vault_tier_%d" % tier: {"lootItem": [_entry(code, amount) for code, amount, _ in loot]}
            for tier, loot in LOOT.items()}


def update_treasure_vault(user):
    """On login: open the vault quests and give the free key of the day to a player out of keys."""
    for name, variant in EXPERIMENTS.items():
        user.setdefault("experiments", {}).setdefault(name, variant)
    user["treasureVaultHighlights"] = highlights()
    player = user["userInfo"]["player"]
    items = player["inventory"]["items"]
    if items.get(KEY, 0) <= 0 and _now() >= float(player.get("treasureVaultOpenTS") or 0) + FREE_KEY_AFTER:
        items[KEY] = 1
        print("Treasure vault: free key")


def spin_response(mode, tier):
    tier = int(tier)
    if tier not in LOOT:
        return _response({"treasureVaultHighlights": highlights()})
    keys, cash = costs(tier)
    if int(mode) == MODE_BUY:
        _player()["cash"] -= cash
    else:
        _items()[KEY] = max(0, _items().get(KEY, 0) - keys)
        _player()["treasureVaultOpenTS"] = int(_now())
    loot = LOOT[tier]
    code, amount, _ = random.choices(loot, weights=[weight for _, _, weight in loot])[0]
    if code in RESOURCES:
        do_rewards("Treasure Vault", {"_type": code, "_count": str(amount)}, {})
    else:
        do_rewards("Treasure Vault", {"_type": "item", "_item": code, "_count": str(amount)}, {})
    print("Treasure vault", tier, "gives", amount, code)
    return _response({"loot": _entry(code, amount), "treasureVaultHighlights": highlights()})
