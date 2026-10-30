"""The Bounty Center (BCB).

A quest gives the building at level 20; it is built from four parts like other part buildings. Activated for
energy (energyRequiredPerLevel of the item), it stays on for an hour, then cools down before it can be activated
again; cash skips the cooling. While it is on, each battle won against a player who is at most 10 levels below
gives Liberty Bonds (xk01). The client counts the bonds itself (BountyCenterManager); the server keeps the same
rules so that the bonds and the quest stay after a reload.
"""
import time

from flask import session

from game_settings import lookup_item_by_code
from quest_engine import handle_quest_progress, progress_action, all_lambda, do_rewards, start_missed_quests, \
    matches_requirement, lookup_quest
import bot_empires
from state_machine import do_costs

BUILDING = "BCB"
BOND = "xk01"
STEP = "activateBountyCenter"
ACTIVE_PERIOD = 60 * 60
SKIP_COST = 12
LEVEL_DIFF = 10
EXPERIMENTS = {"empire_bounty_master": 3}  # unlocks the quests that give the building
QUESTS = ("QBCB_1a", "QBCB_1b")  # the first gives BCB, the second has it built, its sequel has it used


def _now():
    return time.time()


def _player():
    return session['user_object']["userInfo"]["player"]


def _variant(name):
    return int(session['user_object'].get("experiments", {}).get(name, 0) or 0)


def _state():
    return _player().setdefault("bountyCenter", {"lastActivated": 0, "bountyBonds": 0})


def energy_required():
    """Energy of the player's level bracket ("20,36,56|6,8,10": from level 20 6 energy...), then the experiment."""
    levels, energies = [[int(v) for v in part.split(",")]
                        for part in lookup_item_by_code(BUILDING)["-energyRequiredPerLevel"].split("|")]
    level = int(_player()["level"])
    passed = [energy for needed, energy in zip(levels, energies) if level >= needed]
    return (passed[-1] if passed else 0) + {1: -2, 2: 2, 3: 4}.get(_variant("empire_bounty_energyreqs"), 0)


def cooling_period():
    return {2: 12, 3: 47}.get(_variant("empire_bounty_cooldown_period"), 23) * 60 * 60


def payout():
    return {2: 2, 3: 3}.get(_variant("empire_bounty_payout"), 1)


def is_active():
    return _now() < float(_state()["lastActivated"] or 0) + ACTIVE_PERIOD


def update_bounty_center(user, new_quests, meta):
    """On login: players past level 20 never got the quests, they only start on the level up."""
    for name, variant in EXPERIMENTS.items():
        user.setdefault("experiments", {}).setdefault(name, variant)
    player = user["userInfo"]["player"]
    if not player.get("bountyCenterQuestGiven") and matches_requirement(lookup_quest(QUESTS[0])):
        start_missed_quests(QUESTS, new_quests, meta)
        player["bountyCenterQuestGiven"] = True
        print("Bounty center quests started")


def action_response(step, object_id, request, meta):
    skip_cooling = bool((request or {}).get("skipCooling"))
    do_costs({"-energy": str(energy_required()), "-cash": str(SKIP_COST if skip_cooling else 0)})  # costs are xml strings
    _state()["lastActivated"] = int(_now())
    handle_quest_progress(meta, progress_action(STEP))
    print("Bounty center activated", "skipping cooling" if skip_cooling else "")
    return {"errorType": 0, "userId": 1, "metadata": meta, "data": {"id": object_id}}


def _opponent_level(uid):
    save = bot_empires.find_save(uid)
    return int(save['user_object']["userInfo"]["player"].get("level", 0)) if save else 0


def battle_won(opponent_uid, meta):
    """A battle against a player was won: bonds while the center is on and the opponent is not too weak."""
    level = _opponent_level(opponent_uid)
    if not is_active() or level <= 0 or int(_player()["level"]) - level > LEVEL_DIFF:
        return
    bonds = payout()
    do_rewards("Bounty Center", {"_type": "item", "_item": BOND, "_count": str(bonds)}, meta)
    _state()["bountyBonds"] = int(_state().get("bountyBonds") or 0) + bonds

    def bonds_progress(task, progress, i, extra, *args):
        extra["yield"] = bonds
        return True
    handle_quest_progress(meta, all_lambda(progress_action("libertyBondsViaBountyCenter"), bonds_progress))
    print("Bounty center gives", bonds, BOND)
