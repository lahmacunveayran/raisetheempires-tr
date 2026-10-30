"""The slot machine of global PvP (PU_SlotMachine, opened from the token on the strangers bar).

A spin costs slot tokens (GPTK) or cash (GlobalPVPSlotPullKeyCost / GlobalPVPSlotPullEPCost in gameSettings, by
the empire_globalpvp_slotpull_epcost experiment). The prizes of the machine are known (slotMachineFeatured), how
often each came out was decided by Zynga's server: the weights below make the units rare and the last one, the
grand prize, the rarest.
"""
import random

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
