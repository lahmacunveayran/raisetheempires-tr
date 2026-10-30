"""Bot empires: the strangers of global PvP, offline.

The strangers bar (boxing glove button) lists 15 strangers to fight (GlobalPVPMaxInvasionSlots). Attacking one
goes the same way as attacking a neighbor: visit its world, place the occupation, fight its defenders. Here the
strangers are bots: an empire name, a portrait of the game's own commanders, one of the ally islands as world and a
level that follows the player by the game's own matchmaking steps (GlobalPVPPlayerDelta*: -2, -1, 0, +2, +4), so
every player finds opponents of their level. Defenders are the newest army units of that level.

Bots are not saves: they are not listed with the saves or the neighbors. What changes on them (who occupies
them) is kept in mygames/bot_empires.json. find_save / store_save serve real saves and bots alike.
"""
import json
import os
import random
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
ISLANDS = ["111", "123", "-1", "131", None]  # ally islands with objects, None = the starting island
DELTAS = ("-GlobalPVPPlayerDeltaLowest", "-GlobalPVPPlayerDeltaLower", "-GlobalPVPPlayerDeltaEqual",
          "-GlobalPVPPlayerDeltaHigher", "-GlobalPVPPlayerDeltaHighest")
DEFENDERS = 5
MAX_LEVEL = 100


def _player():
    return session['user_object']["userInfo"]["player"]


def bots():
    return [{"uid": FIRST_UID + i, "name": name, "portrait": PORTRAITS[i % len(PORTRAITS)],
             "island": ISLANDS[i % len(ISLANDS)], "delta": DELTAS[i % len(DELTAS)]} for i, name in enumerate(NAMES)]


def lookup_bot(uid):
    return next((bot for bot in bots() if str(bot["uid"]) == str(uid)), None)


def level(bot):
    delta = int(game_settings['settings']['gamesettings'].get(bot["delta"], 0))
    return max(1, min(MAX_LEVEL, int(_player()["level"]) + delta))


def _read_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def defense_fleet(bot):
    """The newest army units the bot's level allows (no event, cash or Titan part units), picked per bot."""
    bot_level = level(bot)
    units = [i for i in game_settings['settings']['items']['item']
             if isinstance(i.get("unit"), dict) and i.get("-type") == "Buildable" and i.get("-subtype") == "army"
             and i.get("-buyable") == "true" and "requiredDate" not in i and i.get("-contractLocked") != "true"
             and str(i["unit"].get("-strength", "")).isdigit() and not i["-code"].startswith("PT")
             and 1 <= int(i.get("requiredLevel") or 0) <= bot_level]
    newest = sorted(units, key=lambda i: -int(i["requiredLevel"]))[:DEFENDERS * 2]
    picked = random.Random(bot["uid"]).sample(newest, min(DEFENDERS, len(newest)))
    return [i["-code"] + ",,,," for i in picked]


def bot_save(bot):
    """The bot as a save, enough for visiting, occupying and fighting it."""
    island = allies[bot["island"]] if bot["island"] else initial_island
    invaders = _read_state().get(str(bot["uid"]), {}).get("invaders", {})
    return {
        "bot": True,
        "profilePic": bot["portrait"],
        "user_object": {
            "userInfo": {
                "player": {"uid": bot["uid"], "level": level(bot), "xp": 0, "playerResourceType": 3,
                           "socialXpGood": 0, "socialLevelGood": 1, "socialXpBad": 0, "socialLevelBad": 1,
                           "expansions": island.get("expansions") or _player()["expansions"]},
                "world": {"objects": island["objects"], "roadData": island["roads"], "resources": {"coins": 0}},
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
