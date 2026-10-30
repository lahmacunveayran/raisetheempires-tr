"""The Titan lab (MechLab, TL01).

The client builds the lab from eight parts. The first part can be collected at once, the others are locked:
each one is unlocked for cash or by collecting all of the part before it. Missing parts are won in Titan
battles: the client makes the enemy fleet (BM03) itself and adds three of the part on a win.

The client keeps all of this on its side, the server only has to remember it:
- partUnlock: a part bought open, kept in the lab's data["partUnlocks"] like the client does.
- updatePartUnlocks: parts opened by collecting the one before.
- WorldService.mechlabStatus: a Titan battle starts, the part it is for is the prize.
- the battle itself: the server does not know the enemy fleet, so it is made here from BM03 and the prize
  goes to the inventory on a win.
"""
from flask import session

from game_settings import lookup_item_by_code
from quest_engine import simple_list, lookup_quest
from save_engine import lookup_object

LAB = "TL01"
ENEMY_FLEET = "BM03"
PRIZE_COUNT = 3
STEPS = ("partUnlock", "updatePartUnlocks")


def parts(code=LAB):
    """The parts of the building in the order the client shows them."""
    return simple_list(lookup_item_by_code(code).get("part", []))


def part_count(part, code=LAB):
    """How many of the part the client asks for: it depends on the parts experiment of the building."""
    experiment = lookup_item_by_code(code).get("partsExperiment")
    variant = int(session['user_object'].get("experiments", {}).get(experiment, 0) or 0) if experiment else 0
    return int(part.get("-countv%d" % variant if 2 <= variant <= 6 else "-countv1", part.get("-count", 0)))


def _unlocks(obj):
    return obj.setdefault("data", {}).setdefault("partUnlocks", {})


def _items():
    return session['user_object']["userInfo"]["player"]["inventory"]["items"]


def _response(meta):
    return {"errorType": 0, "userId": 1, "metadata": meta, "data": []}


def action_response(step, object_id, request, meta):
    obj = lookup_object(object_id)
    if obj is None:
        print("Titan lab", step, "for missing object", object_id)
        return _response(meta)
    if step == "partUnlock":
        unlock_part(obj, LAB, (request or {}).get("partCode"))
    else:
        update_part_unlocks(obj, LAB)
    return _response(meta)


def unlock_part(obj, code, part_code):
    [part] = [p for p in parts(code) if p["-code"] == part_code] or [None]
    if part is None or part.get("-locked") != "true" or _unlocks(obj).get(part_code):
        print("Titan lab: nothing to unlock for", part_code)
        return
    session['user_object']["userInfo"]["player"]["cash"] -= int(part.get("-unlockCost", 0))
    _unlocks(obj)[part_code] = True
    print("Titan lab: part", part_code, "unlocked for cash")


def update_part_unlocks(obj, code):
    all_parts = parts(code)
    for part in all_parts:
        if "-unlocks" in part and _items().get(part["-code"], 0) >= part_count(part, code):
            unlocked = all_parts[int(part["-unlocks"])]["-code"]
            if not _unlocks(obj).get(unlocked):
                _unlocks(obj)[unlocked] = True
                print("Titan lab: part", unlocked, "unlocked by collecting", part["-code"])


def status_response(params):
    """A Titan battle starts: params {"index": part index, "partsItemCode": "TL01"}."""
    all_parts = parts(params.get("partsItemCode") or LAB)
    index = int(params.get("index", -1))
    old = session.get("mechlab")
    if old and old["fleet"]:  # a battle left by retreating: its fleet comes back at full strength
        session.get("fleets", {}).pop(old["fleet"], None)
    session["mechlab"] = {"prize": all_parts[index]["-code"] if 0 <= index < len(all_parts) else None,
                          "fleet": None}
    print("Titan battle for", session["mechlab"]["prize"])
    return _response({"newPVE": 0})


def register_enemy_fleet(params):
    """The client made the enemy fleet itself: add it to the fleets the battle engine knows."""
    mechlab = session.get("mechlab")
    target = params.get("target")
    if not mechlab or mechlab["fleet"] or not target or target in session.get("fleets", {}):
        return
    if not (target.startswith("fleet") or (mechlab["prize"] and mechlab["prize"] in target)) or lookup_quest(target):
        return
    baddies = simple_list(lookup_item_by_code(ENEMY_FLEET)["baddie"])
    session.setdefault("fleets", {})[target] = [{"-" + baddie["-item"]: "1"} for baddie in baddies]
    mechlab["fleet"] = target
    print("Titan enemy fleet", target)


def fleets(params):
    """(enemy units, own units) of a Titan battle."""
    from battle_engine import get_last_fleet_name
    own = session["fleets"].get(params.get("fleet")) or session["fleets"][get_last_fleet_name()]
    enemy = [lookup_item_by_code(baddy[1:]) for sub_fleet in session["fleets"][session["mechlab"]["fleet"]]
             for baddy, count in sub_fleet.items() for i in range(int(count))]
    return enemy, [lookup_item_by_code(unit.split(',')[0]) for unit in own]


def is_battle(params):
    mechlab = session.get("mechlab")
    return bool(mechlab and mechlab["fleet"] and
                mechlab["fleet"] in (params.get("target"), params.get("name"), params.get("fleet")))


def battle_won(params):
    """Gives the prize of a won Titan battle, False if it was some other battle."""
    if not is_battle(params):
        return False
    prize = session["mechlab"]["prize"]
    if prize:
        _items()[prize] = _items().get(prize, 0) + PRIZE_COUNT
        print("Titan battle won:", PRIZE_COUNT, "x", prize)
    session["mechlab"] = None
    return True


def battle_lost():
    mechlab = session.get("mechlab")
    if mechlab and mechlab["fleet"]:
        session.get("fleets", {}).pop(mechlab["fleet"], None)
        session["mechlab"] = None
