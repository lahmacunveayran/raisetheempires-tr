"""Bot empires: the strangers of global PvP, offline.

The strangers bar (boxing glove button) lists 15 strangers to fight (GlobalPVPMaxInvasionSlots), one after the
other: the next one opens when the one before is beaten. Attacking one goes the same way as attacking a neighbor:
visit its world, place the occupation, fight its defenders. Here the strangers are bots: an empire name, a portrait
of the game's own commanders, an ally island as world and a level that follows the player by the game's own
matchmaking steps (GlobalPVPPlayerDelta*: -2, -1, 0, +2, +4), three bots a step, the easy ones first.

A bot is as strong as a player of its level would be. Its defenders mirror the player's best squad (the strongest
units of one subtype, as many as fit in a battle): one defender for each of the player's units, of the same kind
(tank, antitank, artillery) and as strong as that unit times STRENGTH_PER_LEVEL to the power of the level
difference. STRENGTH_PER_LEVEL is how much stronger the game's own units get a level (a fit over the army units,
about 4%). The kind matters more than the level: with the battle rules of battle_engine a squad wins nearly all
battles against defenders its kinds beat and few against defenders that beat them, so a bot of another kind mix
than the player would be far too easy or far too hard. Air and navy units are mirrored by the army kind that fares
the same against the player's squad; support units do not fight. The game's units come in steps of strength, so
the defenders are the mix of steps whose ratios to the player's units are on average the level difference and each
close to it. The enemy AI (battle_engine.ai_best_attack) goes for the player's most dangerous unit, so an exact
mirror of the player's own level wins about 63% of the battles; the bots are made HANDICAP levels weaker than they
show, which makes the bot of the player's level an even match. So made, random squads of level 10 to 95 won about
58%, 54%, 49%, 39% and 33% of the battles against the five steps (test/bot_empires_test.py plays them with the
engine's rules). The defenders are the regular army units of the bot's level whose battle animations are all in the
game's assets; bots differ by the models they pick among units of the same kind and strength. The world of a bot
grows with its level: the ally islands from the smallest to the largest town.

Bots are not saves: they are not listed with the saves or the neighbors. What changes on them (who occupies
them) is kept in mygames/bot_empires.json. find_save / store_save serve real saves and bots alike.
"""
import itertools
import json
import math
import os
import time

from flask import session

from game_settings import allies, initial_island, game_settings, lookup_item_by_code
from save_engine import get_saves, store_session, my_games_path

STATE_PATH = os.path.join(my_games_path(), "bot_empires.json")
FIRST_UID = 900_000_000_001
FIGHT_LIST_DURATION = 24 * 60 * 60  # GlobalPVPFightListDuration
NAMES = ["Demir Kartal", "Kızıl Şahin", "Gök Bozkurt", "Fırtına Ordusu", "Çelik Kale", "Yıldırım Taburu",
         "Kara Kartal", "Altın Aslan", "Mavi Yelken", "Boz Ayı", "Ateş Kalkanı", "Sarp Kayalık", "Gece Baykuşu",
         "Kum Fırtınası", "Buz Dağı"]
# the game's commanders (templates/img/avatars), no real people
PORTRAITS = ["10_ArmyCP_04_100.png", "11_ArmyCP_03_100.png", "12_ArmyCP_02_100.png", "13_ArmyCP_01_100.png",
             "14_AirForceCP_04_100.png", "15_AirForceCP_03_100.png", "16_AirForceCP_02_100.png",
             "17_AirForceCP_01_100.png", "4_NavyCP_04_100.png", "5_NavyCP_03_100.png", "6_NavyCP_02_100.png",
             "7_NavyCP_01_100.png", "8_HansCP_100.png", "9_ArtCP_100.png"]
DELTAS = ("-GlobalPVPPlayerDeltaLowest", "-GlobalPVPPlayerDeltaLower", "-GlobalPVPPlayerDeltaEqual",
          "-GlobalPVPPlayerDeltaHigher", "-GlobalPVPPlayerDeltaHighest")
BOTS_PER_DELTA = 3
SQUAD = 5  # units a side brings to a battle
MAX_LEVEL = 100
ISLAND_TOP_LEVEL = 80  # from this level on a bot lives on the largest island
GRADES = {"poor": 0, "good": 1, "great": 2}  # battle_engine.get_combat_chain_grade
# the kinds that fight by the battle chain (not support units, not the NPC anti air)
FIGHTING_KINDS = {chain["-type"] for chain in game_settings['settings']['combatChain']['chain'] if chain.get("-great")}
CHOICES = 4  # strengths tried for each defender, the nearest to its own
# how much each defender's distance from its own strength counts beside the squad's average: with 0.5 about one
# defender in 60 is more than 1.5 times off (most where the bot's level has no closer unit), one in 8 with 0
SPREAD = 0.5
HANDICAP = 2.5  # levels the bots are weaker than they show: the bot of the player's level wins half the battles
# army units whose battle animations are missing from the kept assets (test_bot_units_have_their_animations)
MISSING_ANIMATIONS = {"U105", "UN29", "UN30", "UN31", "V04", "V05"}


def _player():
    return session['user_object']["userInfo"]["player"]


def _strength(item):
    return int(item["unit"]["-strength"])


def _kind(item):
    return item["unit"]["-type"].split(",")[0]


def _regular_army():
    """The army units a player buys at a level: no event, cash only, locked, support or Titan units."""
    return [i for i in game_settings['settings']['items']['item']
            if isinstance(i.get("unit"), dict) and i.get("-type") == "Buildable" and i.get("-subtype") == "army"
            and i.get("-buyable") == "true" and "requiredDate" not in i and i.get("-contractLocked") != "true"
            and str(i["unit"].get("-strength", "")).isdigit() and not i["-code"].startswith("PT")
            and int(i.get("requiredLevel") or 0) >= 1]


def _strength_per_level(units):
    """Least squares fit of log(strength) over the required level."""
    points = [(int(i["requiredLevel"]), math.log(_strength(i))) for i in units]
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / sum((x - mean_x) ** 2 for x, _ in points)
    return math.exp(slope)


STRENGTH_PER_LEVEL = _strength_per_level(_regular_army())
DEFENDER_POOL = [i for i in _regular_army() if _kind(i) in ("tank", "antitank", "artillery")
                 and i["-code"] not in MISSING_ANIMATIONS]
UNITS_BY_NAME = {i["-name"]: i for i in game_settings['settings']['items']['item'] if isinstance(i.get("unit"), dict)}


def _town_size(island):
    return sum(1 for o in island.get("objects") or [] if o.get("itemName") in BUILDING_NAMES)


BUILDING_NAMES = {i["-name"] for i in game_settings['settings']['items']['item'] if i.get("-type") == "building"}
ISLANDS = sorted([None] + [uid for uid, ally in allies.items() if ally.get("objects")],
                 key=lambda uid: _town_size(allies[uid] if uid else initial_island))  # None: the starting island


def bots():
    return [{"uid": FIRST_UID + i, "name": name, "portrait": PORTRAITS[i % len(PORTRAITS)],
             "delta": DELTAS[min(i // BOTS_PER_DELTA, len(DELTAS) - 1)], "index": i}
            for i, name in enumerate(NAMES)]


def lookup_bot(uid):
    return next((bot for bot in bots() if str(bot["uid"]) == str(uid)), None)


def level_delta(bot):
    return int(game_settings['settings']['gamesettings'].get(bot["delta"], 0))


def level(bot):
    return max(1, min(MAX_LEVEL, int(_player()["level"]) + level_delta(bot)))


def island(bot):
    return ISLANDS[min(len(ISLANDS) - 1, (level(bot) - 1) * (len(ISLANDS) - 1) // (ISLAND_TOP_LEVEL - 1))]


def _read_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def _unit_strength(item):
    """How strong the player's unit fights: Titans grow with the level, research upgrades add up."""
    from battle_engine import handle_strength_upgrades
    from quest_engine import simple_list
    if str(item["unit"].get("-strength", "")).isdigit():
        strength = int(item["unit"]["-strength"])
    else:
        entries = simple_list(item["unit"].get("strengths", {}).get("entry"))
        if not entries:
            return 0
        player_level = int(_player()["level"])
        strength = int(next((e for e in entries if player_level < int(e["-level"])), entries[-1])["-strength"])
    return handle_strength_upgrades(strength, item)


def player_squad():
    """The player's best squad, [(kind, strength)] strongest first: the strongest fighting units of the subtype
    (army, air, navy) that make the strongest squad."""
    subtypes = {}
    for obj in session['user_object']["userInfo"]["world"]["objects"]:
        item = UNITS_BY_NAME.get(obj.get("itemName"))
        fights = item and item.get("-subtype") in ("army", "air", "navy") and _kind(item) in FIGHTING_KINDS
        strength = _unit_strength(item) if fights else 0
        if strength > 0:
            subtypes.setdefault(item["-subtype"], []).append((_kind(item), strength))
    squads = [sorted(units, key=lambda unit: unit[1], reverse=True)[:SQUAD] for units in subtypes.values()]
    return max(squads, key=lambda squad: sum(strength for _, strength in squad), default=[])


def _advantage(kind, squad):
    """How the kind fares against the squad: the grades of its hits on the squad less those of the squad's on it."""
    from battle_engine import get_combat_chain_grade
    return sum(GRADES[get_combat_chain_grade(kind, other)] - GRADES[get_combat_chain_grade(other, kind)]
               for other, _ in squad)


def defense_fleet(bot):
    """The bot's squad: a defender for each unit of the player's best squad, of its kind (or the army kind that fares
    the same against the squad) and its strength times the level difference, from the regular army units of the
    bot's level. A player without units meets the weakest one."""
    units = [i for i in DEFENDER_POOL if int(i["requiredLevel"]) <= level(bot)]
    squad = player_squad()
    if not squad:
        return [min(units, key=_strength)["-code"] + ",,,,"]
    factor = STRENGTH_PER_LEVEL ** (level(bot) - int(_player()["level"]) - HANDICAP)
    kinds = sorted({_kind(i) for i in units})
    slots = [(min(kinds, key=lambda k: (abs(_advantage(k, squad) - _advantage(kind, squad)), k != kind)),
              strength * factor) for kind, strength in squad]
    options = [sorted({_strength(i) for i in units if _kind(i) == kind}, key=lambda s: abs(math.log(s / target)))
               [:CHOICES] for kind, target in slots]
    strengths = min(itertools.product(*options), key=lambda strengths: _error(slots, strengths))
    picked = []
    for slot, ((kind, _), strength) in enumerate(zip(slots, strengths)):
        models = sorted((i for i in units if _kind(i) == kind and _strength(i) == strength), key=lambda i: i["-code"])
        picked.append(models[(bot["index"] + slot) % len(models)])
    return [i["-code"] + ",,,," for i in sorted(picked, key=_strength, reverse=True)]


def _error(slots, strengths):
    """How far the strengths are from those of the slots [(kind, strength)]. A hit takes a share of the target's
    strength that grows with the ratio of the strengths (battle_engine), so what counts is the ratio of each
    defender to its slot: that they make up for one another (their logs add up to nothing) and that each is close."""
    logs = [math.log(strength / target) for (_, target), strength in zip(slots, strengths)]
    return (abs(sum(logs)) + SPREAD * sum(map(abs, logs))) / len(logs)


def bot_save(bot):
    """The bot as a save, enough for visiting, occupying and fighting it."""
    uid = island(bot)
    world = allies[uid] if uid else initial_island
    invaders = _read_state().get(str(bot["uid"]), {}).get("invaders", {})
    return {
        "bot": True,
        "profilePic": bot["portrait"],
        "user_object": {
            "userInfo": {
                "player": {"uid": bot["uid"], "level": level(bot), "xp": 0, "playerResourceType": 3,
                           "socialXpGood": 0, "socialLevelGood": 1, "socialXpBad": 0, "socialLevelBad": 1,
                           "expansions": world.get("expansions") or _player()["expansions"]},
                "world": {"objects": world["objects"], "roadData": world["roads"], "resources": {"coins": 0}},
                "worldName": bot["name"] + " İmparatorluğu",
                "titanName": bot["name"],
            },
            "pvp": {"invaders": invaders},
        },
    }


def find_save(uid):
    """The save of a player or a bot by uid, None if there is none."""
    bot = lookup_bot(uid)
    if bot:
        return bot_save(bot)
    return next((save for save in get_saves() if str(save['user_object']["userInfo"]["player"]["uid"]) == str(uid)),
                None)


def store_save(save):
    if save.get("bot"):
        state = _read_state()
        uid = str(save['user_object']["userInfo"]["player"]["uid"])
        state.setdefault(uid, {})["invaders"] = save['user_object']["pvp"]["invaders"]
        _write_state(state)
    else:
        store_session(save)


def all_saves():
    return get_saves() + [bot_save(bot) for bot in bots()]


def info(bot):
    """The stranger as the client reads it (PVPManager.updateGlobalPVPInfo)."""
    return {"uid": bot["uid"], "coins": 0, "xp": 0, "level": level(bot), "resource": 3,
            "socialXpGood": 0, "socialLevelGood": 1, "socialXpBad": 0, "socialLevelBad": 1, "dominanceRank": 1,
            "snUser": {"name": bot["name"], "image": "img/avatars/" + bot["portrait"], "gender": "m"},
            "tending": {"actions": 0}}


def _batch():
    """The fight list of the day: the wins count until it is renewed."""
    batch = _player().setdefault("globalPVPBatch", {"ts": 0, "wins": 0})
    if time.time() >= batch["ts"] + FIGHT_LIST_DURATION:
        batch.update(ts=int(time.time()), wins=0)
    return batch


def fight_list():
    batch = _batch()
    return {"ts": batch["ts"], "wins": batch["wins"], "fightList": [str(bot["uid"]) for bot in bots()],
            "awardClaimed": False, "info": [info(bot) for bot in bots()]}


def battle_won(uid):
    if lookup_bot(uid):
        _batch()["wins"] += 1
        print("Bot empire beaten:", lookup_bot(uid)["name"], "wins", _batch()["wins"])
