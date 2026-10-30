"""Timed parts events: Mount Losavius (volcano), Magnetic Snare (meteorite), Deep Sea Drill, Cyclone and Nuclear Power.

Each event was a few weeks long in 2012. A quest asks for six building parts (one of them can be had each day) and for
the event building on the water to be activated; the faster it is done, the bigger the reward. When the time runs
out the building pays a consolation instead.

What the client needs (reverse engineered from the *Manager, *DialogState and *PartsGather classes):
  user.experiments        the item's requiredExperiment (empire_*_master = 3).
  world.objects           the event building in state 1. The client does not create it, the server has to place it.
  gameSettings.xml        <volcanoPower>, <meteoriteMining>, ... <requiredDate start end/>: the client counts the days
                          left, which part is available today and the reward tier from these dates, so they are moved
                          to the days the event runs for this player.
  questSettings.xml       the quest's dates and dated rewards, moved the same way so the client shows the reward the
                          server gives.

Activating sends setState (state 1 -> 2) after the client removed the parts locally; the quest engine completes the
quest on that state change and the parts and the building are then taken away here. When the time is up the client
shows a popup and sends the event's collect step (collectEnergy, collectMeteoriteCoins, ...); before this module the
server ignored those steps.

The client fetches gameSettings.xml and questSettings.xml before it logs in and without the session cookie, so the
running event is also kept in a file. A new event is therefore announced on one login and starts on the next one,
on the day the settings carrying its dates are first served.

Only the meteorite event has its own parts dialog in the assets; the others use it too (they read the same fields).
Missing part icons are replaced by the event's quest icon and the missing nuclear power plant image by its quest
icon. The Elite Oton Battleship event (VolcanoReskin6) has a different dialog and no images at all, so it is left out.
"""
import datetime
import json
import os
import re

from flask import session

import quest_engine
from game_settings import lookup_item_by_code
from quest_engine import handle_quest_progress, new_quest_with_sequels, progress_inventory_count, get_tasks, \
    lookup_quest, do_quest_rewards, merge_quest_progress
from quest_trees import ITEMS_BY_NAME
from save_engine import my_games_path
from megaseries import water_spot

MIN_LEVEL = 15
EXPERIMENT_VARIANT = 3
TOKEN_REWARD_COINS = 1000  # TOKEN_REWARD_COIN_COUNT of the managers
CONSTRUCTED = "1"
ACTIVATED = "2"
QUEST_ICONS = "assets/game/quests/Quests_Icons_1.swf/"
PARTS_DIALOG = "PotOfOre_PartsGather"


def _item(code, count):
    return {"_type": "item", "_item": code, "_count": str(count)}


def _resource(kind, count):
    return {"_type": kind, "_count": str(count)}


def _ores(count):
    return [_resource("nrare%d" % i, count) for i in range(5)]


# tiers: (last day + 1, rewards), counted from the first day of the event; the dates come from the 2012 quests
EVENTS = [
    {"key": "volcanoPower", "code": "BB28", "quest": "QVP", "start": datetime.date(2012, 6, 21), "days": 27,
     "experiment": "empire_volcano_power_master", "collect": "collectEnergy", "dialog": "Volcano_PartsGather",
     "icon": QUEST_ICONS + "VolcanoPowerQuestIUcon_01_96.png",
     "tiers": [(15, [_item("EN8", 3)]), (21, [_item("EN8", 2)]), (27, [_item("EN8", 1)])]},
    {"key": "meteoriteMining", "code": "BB29", "quest": "QBB29", "start": datetime.date(2012, 8, 3), "days": 24,
     "experiment": "empire_meteoritemining_master", "collect": "collectMeteoriteCoins", "dialog": None,
     "icon": QUEST_ICONS + "PotOfOreSevenColor_01_96.png", "always": [_item("BB30", 1)],
     # B870 in QBB29 is only the picture of the ore, the ore itself came from the hidden quests QBB29_01..04
     "tiers": [(6, _ores(1000)), (12, _ores(600)), (18, _ores(300)), (24, _ores(100))]},
    {"key": "deepSeaDrill", "code": "BB33", "quest": "QBB33", "start": datetime.date(2012, 8, 24), "days": 24,
     "experiment": "empire_deepseadrill_master", "collect": "collectDeepSeaDrillCoins",
     "dialog": "DeepSeaDrill_PartsGather", "icon": QUEST_ICONS + "DeepSeaDrillQuestIcon_01_96.png",
     "tiers": [(6, [_resource("oil", 10000)]), (12, [_resource("oil", 6000)]), (18, [_resource("oil", 3000)]),
               (24, [_resource("oil", 1500)])]},
    {"key": "cyclonePower", "code": "BB34", "quest": "QCP", "start": datetime.date(2012, 9, 6), "days": 18,
     "experiment": "empire_cyclone_power_master", "collect": "collectCycloneCoins", "dialog": "Cyclone_PartsGather",
     "icon": QUEST_ICONS + "Cyclone_01_96.png",
     "tiers": [(6, [_item("EN8", 3)]), (12, [_item("EN8", 2)]), (18, [_item("EN8", 1)])]},
    {"key": "nuclearPower", "code": "BB36", "quest": "QNP", "start": datetime.date(2012, 10, 5), "days": 24,
     "experiment": "empire_nps_master", "collect": "collectNuclearCoins", "dialog": "NuclearPlant_PartsGather",
     "icon": QUEST_ICONS + "NuclearPowerplant_01_96.png",
     "tiers": [(6, [_item("N37", 4)]), (12, [_item("N37", 3)]), (18, [_item("N37", 2)]), (24, [_item("N37", 1)])]},
]
BY_KEY = {e["key"]: e for e in EVENTS}
BY_CODE = {e["code"]: e for e in EVENTS}
BY_QUEST = {e["quest"]: e for e in EVENTS}
COLLECT_STEPS = {e["collect"]: e for e in EVENTS}

# quests of these events (and of the left out one) are only started by this module
quest_engine.gated_quests.update([e["quest"] for e in EVENTS] + ["QBB29_01", "QBB29_02", "QBB29_03", "QBB29_04",
                                                                 "QVR6"])

# images missing from the assets: in the parts dialog, the quest and the island
MISSING_ICONS = {
    "BB28": "assets/game/buildables/VolcanoPower_Icons_0.swf/",
    "BB33": "assets/game/buildables/Buildables_Icons_1.swf/DSD_",
    "BB34": "assets/game/buildables/Buildables_Icons_1.swf/CP_",
    "BB36": "assets/game/buildables/Buildables_Icons_1.swf/NPPL_",
}
NUCLEAR_IMAGE = "assets/game/buildings/Buildings_Buildables_03.swf/Bldg_Blds_NuclearPowerplant_SW.png"


def parts(event):
    """[(part code, count needed)] in the order the client shows them, one of them each day."""
    raw = lookup_item_by_code(event["code"]).get("part", [])
    return [(p["-code"], int(p.get("-count", p.get("-countv0", 0)))) for p in (raw if isinstance(raw, list) else [raw])]


def _today():
    return datetime.date.today()


def _date(text):
    return datetime.date.fromisoformat(text) if text else None


def _end(event, start):
    return start + datetime.timedelta(days=event["days"])


def _client_date(day):
    return day.strftime("%m/%d/%Y")


# --- running event kept in a file for the settings served before login -------------------------------------------

def _state_file():
    return os.path.join(my_games_path(), "event_buildings.json")


def _read_file():
    try:
        with open(_state_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("event") in BY_KEY else None
    except (OSError, ValueError):
        return None


def _write_file(event_key, start):
    try:
        with open(_state_file(), "w") as f:
            json.dump({"event": event_key, "start": start}, f)
    except OSError as error:
        print("Could not store the running event", error)


def served_event():
    """(event, first day) to put into the settings; a just announced event starts today."""
    data = _read_file()
    if not data:
        return None
    if not data.get("start"):
        data["start"] = _today().isoformat()
        _write_file(data["event"], data["start"])
        print("Event", data["event"], "starts", data["start"])
    return BY_KEY[data["event"]], _date(data["start"])


# --- settings served to the client ----------------------------------------------------------------------------------

def _item_block(xml, code):
    at = xml.find(' code="%s"' % code)
    if at < 0:
        return None
    start = xml.rfind("<item ", 0, at)
    end = xml.find("</item>", at)
    return (start, end) if start >= 0 and end >= 0 else None


def _patch_item(xml, code, patch):
    span = _item_block(xml, code)
    if not span:
        return xml
    start, end = span
    return xml[:start] + patch(xml[start:end]) + xml[end:]


def _icon_patch(event):
    prefix = MISSING_ICONS.get(event["code"])
    return lambda block: re.sub(r'url="%s[^"]*"' % re.escape(prefix), 'url="%s"' % event["icon"], block) \
        if prefix else block


def _nuclear_patch(block):
    block = re.sub(r'<image name="(sw|Active)"[^>]*url="%s"[^>]*>.*?</image>' % re.escape(NUCLEAR_IMAGE),
                   r'<image name="\1" offset="0,0" url="%s"/>' % BY_CODE["BB36"]["icon"], block, flags=re.S)
    return block.replace("assets/game/buildings/Buildings_Icons.swf/Bldg_Blds_CyclonePower",
                         "assets/game/decorations/Decorations_Icons.swf/Bldg_Blds_CyclonePower")


def _required_date(start, end):
    return '<requiredDate start="%s" end="%s"/>' % (_client_date(start), _client_date(end))


def patch_settings_xml(xml, running=None):
    """Make the events work with the assets there are, and give the running one its dates."""
    for event in EVENTS:
        if event["dialog"]:
            xml = _patch_item(xml, event["code"], lambda block, e=event: block.replace(
                'buildingPartsDialog="%s"' % e["dialog"], 'buildingPartsDialog="%s"' % PARTS_DIALOG))
        for code in [event["code"]] + [p for p, _ in parts(event)]:
            xml = _patch_item(xml, code, _icon_patch(event))
    xml = _patch_item(xml, "BB36", _nuclear_patch)
    if running:
        event, start = running
        xml = re.sub(r"<%s>.*?</%s>" % (event["key"], event["key"]),
                     "<%s>%s</%s>" % (event["key"], _required_date(start, _end(event, start)), event["key"]),
                     xml, count=1, flags=re.S)
    return xml


def _reward_xml(reward, start=None, end=None):
    attributes = 'type="%s"' % reward["_type"]
    if "_item" in reward:
        attributes += ' item="%s"' % reward["_item"]
    attributes += ' count="%s"' % reward["_count"]
    if start is None:
        return "<reward %s/>" % attributes
    return "<reward %s>%s</reward>" % (attributes, _required_date(start, end))


def _quest_block(xml, name):
    begin = xml.find('<quest name="%s"' % name)
    end = xml.find("</quest>", begin)
    return (begin, end) if begin >= 0 and end >= 0 else None


def patch_quest_xml(xml, running=None):
    """Missing task icons, and for the running event the quest's dates and the rewards the server gives."""
    for event in EVENTS:
        span = _quest_block(xml, event["quest"])
        if span and event["code"] in MISSING_ICONS:
            begin, end = span
            xml = xml[:begin] + re.sub(r'icon="%s[^"]*"' % re.escape(MISSING_ICONS[event["code"]]),
                                       'icon="%s"' % event["icon"], xml[begin:end]) + xml[end:]
    if not running:
        return xml
    event, start = running
    span = _quest_block(xml, event["quest"])
    if not span:
        return xml
    begin, end = span
    tasks_end = xml.find("</tasks>", begin, end)
    if tasks_end < 0:
        return xml
    head = re.sub(r"<requiredDate [^>]*/>", _required_date(start, _end(event, start)), xml[begin:tasks_end], count=1)
    rewards = [_reward_xml(r) for r in event.get("always", [])]
    first = 0
    for last, tier in event["tiers"]:
        tier_start, tier_end = start + datetime.timedelta(days=first), start + datetime.timedelta(days=last)
        rewards += [_reward_xml(r, tier_start, tier_end) for r in tier]
        first = last
    return xml[:begin] + head + "</tasks>" + "".join(rewards) + xml[end:]


# --- server side ----------------------------------------------------------------------------------------------------

def _state(user):
    state = user["userInfo"]["player"].get("eventBuildings")
    if not isinstance(state, dict):
        state = user["userInfo"]["player"]["eventBuildings"] = {"next": 0, "event": None, "start": None}
    return state


def _running(user):
    state = _state(user)
    if state.get("event") in BY_KEY and state.get("start"):
        return BY_KEY[state["event"]], _date(state["start"])
    return None


def tier_rewards(event, start, today=None):
    day = ((today or _today()) - start).days
    rewards = next((tier for last, tier in event["tiers"] if day < last), event["tiers"][-1][1])
    return event.get("always", []) + rewards


def _quest_rewards(quest_name):
    def rewards():
        running = _running(session['user_object'])
        event = BY_QUEST[quest_name]
        start = running[1] if running and running[0] is event else _today()
        return tier_rewards(event, start)
    return rewards


for _event in EVENTS:
    quest_engine.reward_overrides[_event["quest"]] = _quest_rewards(_event["quest"])


def _buildings(world, event):
    name = lookup_item_by_code(event["code"])["-name"]
    return [o for o in world.get("objects", []) if o.get("itemName") == name]


def _place(world, event):
    if _buildings(world, event):
        return True
    item = lookup_item_by_code(event["code"])
    spot = water_spot(world, max(int(item.get("sizeX", 3)), int(item.get("sizeY", 3)), 3))
    if spot is None:
        print("No water spot for event", event["key"])
        return False
    world["globalObjectId"] += 1
    world["objects"].append({"id": world["globalObjectId"], "itemName": item["-name"], "position": "%d,%d,0" % spot,
                             "referenceItem": None, "state": CONSTRUCTED})
    print("Event", event["key"], "building placed at", spot)
    return True


def _give_part_of_the_day(user, event, start):
    """Friends used to send the parts; now the part of the day comes by itself when the player logs in that day."""
    state = _state(user)
    today = _today()
    day = (today - start).days
    if not 0 <= day < event["days"] or state.get("granted") == today.isoformat():
        return False
    state["granted"] = today.isoformat()
    code, count = parts(event)[day % len(parts(event))]
    items = user["userInfo"]["player"]["inventory"]["items"]
    if items.get(code, 0) >= count:
        return False
    items[code] = count
    print("Event", event["key"], "part of day", day + 1, code, "x", count)
    return True


def _announce(user, event):
    state = _state(user)
    state.update({"event": event["key"], "start": None, "granted": None})
    _write_file(event["key"], None)
    print("Event", event["key"], "announced, it starts on the next login")


def _start(user, event, start, new_quests, meta):
    if not _place(user["userInfo"]["world"], event):
        return False
    _state(user)["start"] = start.isoformat()
    _give_part_of_the_day(user, event, start)
    session['quests'][:] = [q for q in session['quests'] if q['name'] != event["quest"]]  # played before
    new_quest_with_sequels(event["quest"], new_quests, meta, force=True)
    print("Event", event["key"], "started", start)
    return True


def _finish(user, event):
    """The event is over: take the parts and the building away and announce the next event."""
    items = user["userInfo"]["player"]["inventory"]["items"]
    for code, count in parts(event):
        if code in items:
            items[code] -= min(count, items[code])
            if items[code] <= 0:
                del items[code]
    world = user["userInfo"]["world"]
    for building in _buildings(world, event):
        world["objects"].remove(building)
    state = _state(user)
    state["next"] = (EVENTS.index(event) + 1) % len(EVENTS)
    _announce(user, EVENTS[state["next"]])


def update_event_buildings(user, new_quests, meta):
    """Called on login: start the announced event, give the part of the day, announce the first event."""
    experiments = user.setdefault("experiments", {})
    for event in EVENTS:
        experiments[event["experiment"]] = EXPERIMENT_VARIANT
    if user["userInfo"]["player"].get("level", 0) < MIN_LEVEL:
        return
    state = _state(user)
    if state.get("event") not in BY_KEY:
        _announce(user, EVENTS[state.get("next", 0) % len(EVENTS)])
        return
    event = BY_KEY[state["event"]]
    running = _running(user)
    if running is None:
        served = _read_file()
        if served and served.get("event") == event["key"] and served.get("start"):
            _start(user, event, _date(served["start"]), new_quests, meta)
        else:
            _write_file(event["key"], None)  # file lost: start with the next settings
        return
    _write_file(event["key"], state["start"])
    if not _buildings(user["userInfo"]["world"], event):
        _place(user["userInfo"]["world"], event)
    if _give_part_of_the_day(user, event, running[1]):
        handle_quest_progress(meta, progress_inventory_count())


def after_state_change(obj, meta):
    """setState on an event building: activating it (state 2) ends the event.

    The quest engine normally completed the quest just before. The client only lets the player activate with all
    parts in its inventory, so if the server counts fewer (it lost some), the quest is completed here all the same."""
    event = BY_CODE.get((ITEMS_BY_NAME.get(obj.get("itemName")) or {}).get("-code"))
    if not event or str(obj.get("state")) != ACTIVATED:
        return
    quest = next((q for q in session['quests'] if q["name"] == event["quest"]), None)
    if quest and not quest["complete"]:
        print("Event", event["key"], "activated with parts missing on the server, completing", event["quest"])
        tasks = get_tasks(lookup_quest(event["quest"]))
        quest.update({"complete": True, "progress": [int(t["_total"]) for t in tasks],
                      "completedTasks": 2 ** len(tasks) - 1})
        do_quest_rewards(lookup_quest(event["quest"]), meta)
        merge_quest_progress([quest], meta.setdefault('QuestComponent', []), "output quest")
    print("Event", event["key"], "activated")
    _finish(session['user_object'], event)


def collect_response(step, object_id, meta):
    """The time ran out and the player collects the consolation (coins, for the volcano energy for the parts)."""
    event = COLLECT_STEPS[step]
    data = {"id": object_id}
    response = {"errorType": 0, "userId": 1, "metadata": meta, "data": data}
    user = session['user_object']
    running = _running(user)
    building = next((o for o in _buildings(user["userInfo"]["world"], event) if o["id"] == object_id), None)
    if not running or running[0] is not event or building is None:
        print("Ignoring", step, "for", object_id, ": not the running event")
        return response
    if _today() < _end(event, running[1]):
        print("Ignoring", step, ": event", event["key"], "runs until", _end(event, running[1]))
        return response
    if step == "collectEnergy":
        items = user["userInfo"]["player"]["inventory"]["items"]
        total = sum(min(items.get(code, 0), count) for code, count in parts(event))
        data["energy"] = {"EN1": total} if total else {}
        if total:
            items["EN1"] = items.get("EN1", 0) + total
        print("Event", event["key"], "expired, energy for the parts:", total)
    else:
        user["userInfo"]["world"]["resources"]["coins"] += TOKEN_REWARD_COINS
        data["coins"] = TOKEN_REWARD_COINS
        print("Event", event["key"], "expired, coins:", TOKEN_REWARD_COINS)
    session['quests'][:] = [q for q in session['quests'] if q['name'] != event["quest"]]
    _finish(user, event)
    return response
