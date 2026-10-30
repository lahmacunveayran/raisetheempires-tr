"""The slot machine of global PvP (PU_SlotMachine, opened from the token on the strangers bar).

A spin costs slot tokens (GPTK) or cash (GlobalPVPSlotPullKeyCost / GlobalPVPSlotPullEPCost in gameSettings, by
the empire_globalpvp_slotpull_epcost experiment). The prizes of the machine are known (slotMachineFeatured), how
often each came out was decided by Zynga's server: the weights below make the units rare and the last one, the
grand prize, the rarest.

The strangers bar shows only for players who opted in to global PvP, with the strangerbar experiments on. There are
no strangers to fight offline, so the fight list is always empty: the bar is there for the machine.
"""
import random
import time

from flask import session

from game_settings import game_settings
from quest_engine import do_rewards
from quest_trees import ITEMS_BY_NAME
from treasure_vault import RESOURCES, _entry, _items, _player, _response

TOKEN = "GPTK"
MODE_BUY, MODE_KEYS = 0, 1
RESOURCE_CODES = {"RG08": "coins", "RG07": "oil", "RG06": "wood"}  # the prizes name these resource items
WEIGHTS = {"Buildable": 4, "consumable": 12, "buildablepart": 12, "resource": 15}
GRAND_PRIZE_WEIGHT = 1
EXPERIMENTS = {"empire_globalpvp_master": 2, "empire_globalpvp_strangerbar_enable": 2}  # the client wants exactly 2


def _cost(setting):
    variant = int(session['user_object'].get("experiments", {}).get("empire_globalpvp_slotpull_epcost", 0) or 0)
    costs = game_settings['settings']['gamesettings'][setting].split(',')
    return int(costs[variant] if variant < len(costs) else costs[0])


def prizes():
    """[(item code or resource, amount, weight)] from slotMachineFeatured, the last tier being the grand prize."""
    featured = game_settings['settings']['slotMachineFeatured']['set']
    infos = sorted(featured[0]["info"] if isinstance(featured, list) else featured["info"], key=lambda i: int(i["-tier"]))
    loot = []
    for i, info in enumerate(infos):
        item = ITEMS_BY_NAME[info["-itemName"]]
        code = RESOURCE_CODES.get(item["-code"], item["-code"])
        weight = GRAND_PRIZE_WEIGHT if i == len(infos) - 1 else WEIGHTS.get(item["-type"], 4)
        loot.append((code, int(info["-amount"]), weight))
    return loot


def update_slot_machine(user):
    """On login: turn on the strangers bar (the info popup that asks to opt in is missing, so opt in already)."""
    user.setdefault("experiments", {}).update(EXPERIMENTS)
    user.setdefault("pvp", {}).setdefault("globalPVPOptIn", True)


def opt_in_response(opt_in):
    session['user_object'].setdefault("pvp", {})["globalPVPOptIn"] = bool(opt_in)
    return _response({})


def fight_list_response():
    return _response({"ts": int(time.time()), "wins": 0, "fightList": [], "awardClaimed": False, "info": []})


def spin_response(mode):
    if int(mode) == MODE_BUY:
        _player()["cash"] -= _cost("-GlobalPVPSlotPullEPCost")
    else:
        _items()[TOKEN] = max(0, _items().get(TOKEN, 0) - _cost("-GlobalPVPSlotPullKeyCost"))
    loot = prizes()
    code, amount, _ = random.choices(loot, weights=[weight for _, _, weight in loot])[0]
    if code in RESOURCES:
        do_rewards("Slot machine", {"_type": code, "_count": str(amount)}, {})
    else:
        do_rewards("Slot machine", {"_type": "item", "_item": code, "_count": str(amount)}, {})
    print("Slot machine gives", amount, code)
    return _response({"loot": _entry(code, amount)})
