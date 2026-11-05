import contextlib
import copy
import functools
import glob
import io
import json
import math
import os
import random
import sys
import xml.etree.ElementTree as ET

import pytest
from flask import Flask, session

import battle_engine
import bot_empires
import client_settings

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRADES = client_settings.CHANCE  # CombatChain.POOR 0, GOOD 1, GREAT 2
UNITS_ASSETS = os.path.join(ROOT, "assets", "sol_assets_octdict", "assets", "game", "units")


def setup_session(monkeypatch, tmp_path, level=85, units=None):
    """A player of the level, with these units in place of the starting ones (V61, U01) if any are given."""
    monkeypatch.setattr(bot_empires, "STATE_PATH", str(tmp_path / "bot_empires.json"))
    monkeypatch.setattr(bot_empires, "get_saves", lambda: [])
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    if units is not None:
        objects = user["userInfo"]["world"]["objects"]
        objects[:] = [o for o in objects if o.get("itemName") not in bot_empires.UNITS_BY_NAME]
        objects += [{"itemName": bot_empires.lookup_item_by_code(code)["-name"]} for code in units]
    session["user_object"] = user
    return user


def strength(code):
    return int(bot_empires.lookup_item_by_code(code.split(",")[0])["unit"]["-strength"])


def kind(code):
    return bot_empires.lookup_item_by_code(code.split(",")[0])["unit"]["-type"].split(",")[0]


def test_fight_list_follows_the_player_level_easy_ones_first(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path)
        data = bot_empires.fight_list()
        assert len(data["fightList"]) == 15  # GlobalPVPMaxInvasionSlots
        assert [i["level"] for i in data["info"]] == [83] * 3 + [84] * 3 + [85] * 3 + [87] * 3 + [89] * 3
        assert all(i["snUser"]["name"] and i["snUser"]["image"].startswith("img/avatars/") for i in data["info"])
        assert len({i["uid"] for i in data["info"]}) == 15
        setup_session(monkeypatch, tmp_path, level=1)
        assert min(i["level"] for i in bot_empires.fight_list()["info"]) == 1


def xml_regular_army():
    """[(required level, strength)] of the army units a player buys at a level, read from the XML with ElementTree
    by the rule of bot_empires' docstring: <item type="Buildable" subtype="army" buyable="true">, not an event unit
    (no <requiredDate>), not contractLocked, a single <unit> with a fixed strength (Titans have none), not a
    Titan part (PT...), a <requiredLevel> of 1 or more. In file order; an item that is in the file twice counts
    twice, as in the item list of game_settings."""
    found = []
    for item in ET.parse(client_settings.PATH).getroot().find("items").findall("item"):
        units = item.findall("unit")
        level = item.findtext("requiredLevel")
        if (item.get("type"), item.get("subtype"), item.get("buyable")) == ("Buildable", "army", "true") and \
                item.find("requiredDate") is None and item.get("contractLocked") != "true" and len(units) == 1 \
                and units[0].get("strength", "").isdigit() and not item.get("code").startswith("PT") \
                and level and int(level) >= 1:
            found.append((int(level), int(units[0].get("strength"))))
    return found


def test_units_get_stronger_by_a_few_percent_a_level():
    """STRENGTH_PER_LEVEL is exp of the least squares slope of ln(strength) over the required level of the regular
    army units of the XML (bot_empires: "a fit over the army units, about 4%"), computed here from the XML."""
    points = [(x, math.log(s)) for x, s in xml_regular_army()]
    assert len(points) >= 20  # enough units for a fit
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / sum((x - mean_x) ** 2 for x, _ in points)
    assert bot_empires.STRENGTH_PER_LEVEL == math.exp(slope)
    assert 1.03 < math.exp(slope) < 1.06  # "about 4%", the docstring's figure


def test_bots_mirror_the_players_best_squad(monkeypatch, tmp_path):
    with app.test_request_context():
        # a level 20 player: four army units and a weaker air squad (U02 bombers)
        setup_session(monkeypatch, tmp_path, level=20, units=["U05", "V62", "V03", "U01", "U02", "U02"])
        squad = [("tank", 100), ("artillery", 80), ("antitank", 60), ("antitank", 30)]
        assert bot_empires.player_squad() == squad
        equal = bot_empires.bots()[6]
        assert bot_empires.level(equal) == 20
        monkeypatch.setattr(bot_empires, "HANDICAP", 0)
        assert sorted((kind(u), strength(u)) for u in bot_empires.defense_fleet(equal)) == sorted(squad)
        monkeypatch.undo()
        setup_session(monkeypatch, tmp_path, level=20, units=["U05", "V62", "V03", "U01", "U02", "U02"])
        # stronger by the step: the product of the strengths grows, the kinds stay
        products = []
        for bot in bot_empires.bots()[::3]:
            fleet = bot_empires.defense_fleet(bot)
            assert sorted(map(kind, fleet)) == sorted(k for k, _ in squad)
            products.append(sum(math.log(strength(u)) for u in fleet))
        assert products == sorted(products) and products[0] < products[2] < products[4]


def test_air_squads_meet_the_army_kinds_that_fare_alike(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path, level=40, units=["UA06", "UA06", "UA06"])
        squad = bot_empires.player_squad()
        assert squad == [("bomber", 200)] * 3
        # tanks and bombers hit each other well; bombers hit antitanks greatly, artillery hits bombers greatly
        assert [kind(u) for u in bot_empires.defense_fleet(bot_empires.bots()[6])] == ["tank"] * 3


def test_only_fighting_units_make_the_squad(monkeypatch, tmp_path):
    with app.test_request_context():
        # army support (UL31, 250) and the NPC anti air (PU6, no battle chain) are left out
        setup_session(monkeypatch, tmp_path, level=40, units=["UL31"] * 5 + ["PU6"] + ["U04"] * 3)
        assert bot_empires.player_squad() == [("tank", 50)] * 3
        assert [kind(u) for u in bot_empires.defense_fleet(bot_empires.bots()[6])] == ["tank"] * 3


def test_a_new_player_meets_starting_units(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path, level=8)
        assert bot_empires.player_squad() == [("artillery", 40), ("antitank", 30)]  # the starting V61 and U01
        assert sorted(map(strength, bot_empires.defense_fleet(bot_empires.bots()[0]))) == [30, 40]
        setup_session(monkeypatch, tmp_path, level=8, units=[])
        assert bot_empires.player_squad() == []
        assert bot_empires.defense_fleet(bot_empires.bots()[0]) == ["U01,,,,"]


def test_defenders_are_regular_army_units_of_the_bots_level(monkeypatch, tmp_path):
    with app.test_request_context():
        for level in (8, 25, 40, 60, 85):
            setup_session(monkeypatch, tmp_path, level=level, units=["UM82", "UM81", "UM80", "UL81", "UL80"])
            for bot in bot_empires.bots():
                fleet = bot_empires.defense_fleet(bot)
                assert 1 <= len(fleet) <= bot_empires.SQUAD
                for unit in fleet:
                    item = bot_empires.lookup_item_by_code(unit.split(",")[0])
                    assert item["-subtype"] == "army" and 1 <= int(item["requiredLevel"]) <= bot_empires.level(bot)
                    assert item["-code"] not in bot_empires.MISSING_ANIMATIONS


def symbol_names():
    sys.path.insert(0, os.path.join(ROOT, "turkce", "araclar"))
    from swf import read_swf
    names = set()
    for path in glob.glob(os.path.join(UNITS_ASSETS, "Units_*.swf")):
        for code, data in read_swf(path)["tags"]:
            if code == 76:  # SymbolClass
                pos = 2
                for _ in range(int.from_bytes(data[:2], "little")):
                    end = data.index(b"\0", pos + 2)
                    names.add(data[pos + 2:end].decode("latin1").removesuffix(".png"))
                    pos = end + 1
    return names


def test_bot_units_have_their_animations():
    names = symbol_names()
    def as_list(value):
        return value if isinstance(value, list) else [value] if value else []

    def missing(item):
        return [a["-name"] for image in as_list(item.get("image")) for a in as_list(image.get("animation"))
                if a["-name"] not in names and a["-name"] + "_Anim" not in names]
    assert {i["-code"] for i in bot_empires._regular_army() if missing(i)} == bot_empires.MISSING_ANIMATIONS


def test_bot_worlds_grow_with_their_level(monkeypatch, tmp_path):
    with app.test_request_context():
        sizes = []
        for level in (1, 20, 40, 60, 80, 100):
            setup_session(monkeypatch, tmp_path, level=level)
            uid = bot_empires.island(bot_empires.bots()[6])
            sizes.append(bot_empires._town_size(bot_empires.allies[uid] if uid else bot_empires.initial_island))
        assert sizes == sorted(sizes) and sizes[0] < sizes[-1]
        setup_session(monkeypatch, tmp_path, level=bot_empires.ISLAND_TOP_LEVEL - 1)
        assert bot_empires.island(bot_empires.bots()[6]) != bot_empires.ISLANDS[-1]
        setup_session(monkeypatch, tmp_path, level=bot_empires.ISLAND_TOP_LEVEL)
        assert bot_empires.island(bot_empires.bots()[6]) == bot_empires.ISLANDS[-1]
        assert bot_empires.island(bot_empires.bots()[6]) == bot_empires.ISLANDS[-1]


# the client's CombatChain, read from gameSettings_with_fixes.xml (client_settings), for units of these kinds
@functools.lru_cache(maxsize=None)
def hit_value(attacker_kind, defender_kind):  # CombatChain.GetAttackingHitValue: (critical, direct)
    return client_settings.settings()["hit_values"][client_settings.grade_of_types([attacker_kind], [defender_kind])]


@functools.lru_cache(maxsize=None)
def hit_chance(attacker_kind, defender_kind):  # CombatChain.GetAttackingHitChance
    return GRADES[client_settings.grade_of_types([attacker_kind], [defender_kind])]


def player_pick(player, bot, player_left, bot_left):
    """The player's hit: the one that takes the largest share of what the target has left, the weakest first."""
    def expected(attacker, defender, defender_left):
        critical, direct = hit_value(attacker[0], defender[0])
        crit = max(0.0, 1 - critical)
        mean = direct * 0.1 + (1 - direct - crit) + crit * 1.5
        return mean * 25 * (3 * attacker[1] + defender_left) / (3 * defender_left + attacker[1]) / 100 * defender[1]

    players = [i for i, s in enumerate(player_left) if s > 0]
    bots = [i for i, s in enumerate(bot_left) if s > 0]
    return max(((a, d) for a in players for d in bots),
               key=lambda p: (min(1, expected(player[p[0]], bot[p[1]], bot_left[p[1]]) / bot_left[p[1]]),
                              -bot_left[p[1]]))


def play(player, bot, roll):
    """One battle with the rules of battle_engine.battle_complete_response: the player hits first, the sides take
    turns, the AI attacks as ai_best_attack does. [(kind, strength)] each side, roll() the random float of the
    battle; the strengths both sides have left."""
    def grade(attacker, defender):
        return hit_chance(attacker[0], defender[0])

    def hit(attacker, defender, defender_left):
        critical, direct = hit_value(attacker[0], defender[0])
        damage = 25 * (3 * attacker[1] + defender_left) / (3 * defender_left + attacker[1]) / 100 * defender[1]
        damage = math.floor(damage * 1000) / 1000
        r = roll()
        damage *= 0.10 if r < direct else 1.5 if r >= critical else 1
        return math.ceil(damage)

    def pick(r, n):  # as3_round: the client's Math.round
        return math.floor(r * (n - 1) + 0.5)

    def best_unit(units, left, other, r):  # ai_best_unit
        alive = [i for i in range(len(units)) if left[i] > 0]
        best = max([grade(units[i], other) for i in alive] + [-1])
        ties = [i for i in alive if grade(units[i], other) == best]
        return (ties[pick(r, len(ties))], best) if ties else (None, -1)

    def ai_attack():  # ai_best_attack: (bot unit, player unit)
        first = roll()
        method_1 = [best_unit(bot, bot_left, player[p], first) + (p,) for p in range(len(player)) if player_left[p] > 0]
        top = max(g for _, g, _ in method_1)
        pairs = [x for x in method_1 if x[1] == top and x[1] >= 0]
        if pairs:
            chosen = pairs[pick(roll(), len(pairs)) if len(pairs) > 1 else 0]
            pairing_1 = (pairs[0][0],) + chosen[1:]  # the engine's "bugged pairings"
        else:
            pairing_1 = None, 0, None
        method_2 = [best_unit(player, player_left, bot[b], first) + (b,) for b in range(len(bot)) if bot_left[b] > 0]
        top_2 = max(g for _, g, _ in method_2)
        threats = [p for p, g, _ in method_2 if g == top_2 and g >= 0]
        pairing_2 = best_unit(bot, bot_left, player[threats[0]], roll()) + (threats[0],) if threats else (None, 0, None)
        ratio = pairing_2[1] / top if top > 0 else 0
        b, _, p = pairing_1 if (ratio < 0.5) ^ (roll() < 0.2) else pairing_2
        return b, p

    player_left, bot_left = [s for _, s in player], [s for _, s in bot]
    for turn in range(500):
        if not any(bot_left) or not any(player_left):
            break
        if turn % 2 == 0:
            a, d = player_pick(player, bot, player_left, bot_left)
            bot_left[d] -= hit(player[a], bot[d], bot_left[d])
            if bot_left[d] <= 1:  # the engine does not leave an enemy at 1
                bot_left[d] = 0
        else:
            b, p = ai_attack()
            player_left[p] = max(0, player_left[p] - hit(bot[b], player[p], player_left[p]))
    return player_left, bot_left


def random_squad(rng, level):
    """3 to 5 recent units of a player of the level."""
    pool = [i["-code"] for i in bot_empires.DEFENDER_POOL if level - 20 <= int(i["requiredLevel"]) <= level]
    return [rng.choice(pool) for _ in range(rng.randint(3, 5))]


class EngineRandom:
    """The random floats of the engine (quest_engine.roll_random_float) from the seeds w and z."""
    def __init__(self, w, z):
        self.w, self.z = w, z

    def __call__(self):
        self.z = 36969 * (self.z & 65535) + (self.z >> 16) & 0xFFFFFFFF
        self.w = 18000 * (self.w & 65535) + (self.w >> 16) & 0xFFFFFFFF
        return math.floor(((self.z << 16) + self.w & 0xFFFFFFFF) / (2 ** 32 - 1) * 1000) / 1000


def engine_play(player_codes, bot_codes, w, z):
    """The battle of play(), the same player picks, but each turn answered by battle_complete_response."""
    world = session["user_object"]["userInfo"]["world"]
    world["randSeedW"], world["randSeedZ"] = w, z
    session["quests"] = []
    session["fleets"] = {"fleet2_1": [c + ",,,," for c in player_codes], "fleet3_1": [{"-" + c: "1"} for c in bot_codes]}
    session["battle"] = None
    player, bot = [(kind(c), strength(c)) for c in player_codes], [(kind(c), strength(c)) for c in bot_codes]
    player_left, bot_left = [s for _, s in player], [s for _, s in bot]
    for turn in range(500):
        if not any(bot_left) or not any(player_left):
            break
        params = {"fleet": "fleet2_1", "target": "fleet3_1", "map": None}
        if turn % 2 == 0:
            params["id"] = list(player_pick(player, bot, player_left, bot_left))
        r = battle_engine.battle_complete_response(params)["data"]
        if session["battle"]:
            player_left, bot_left = list(session["battle"][0]), list(session["battle"][1])
        elif turn % 2 == 0:  # the battle is over, the engine has let it go
            bot_left[r["enemyUnit"]] = r["es"]
        else:
            player_left[r["playerUnit"]] = r["ps"]
    return player_left, bot_left


def test_the_battles_played_here_are_the_engines(monkeypatch, tmp_path):
    """play() is battle_engine's battle: with the engine's random numbers it ends every battle as
    battle_complete_response does, so the balance measured with it is the engine's."""
    monkeypatch.setattr(battle_engine, "report_battle_log", lambda *a: None)
    rng = random.Random(1)
    with app.test_request_context():
        session.sid = "0"
        for level in range(10, 100, 10):
            for _ in range(3):
                units = random_squad(rng, level)
                setup_session(monkeypatch, tmp_path, level=level, units=units)
                bot = bot_empires.bots()[rng.randrange(15)]
                fleet = [u.split(",")[0] for u in bot_empires.defense_fleet(bot)]
                w, z = rng.randrange(1, 2 ** 32), rng.randrange(1, 2 ** 32)
                expected = play([(kind(u), strength(u)) for u in units], [(kind(u), strength(u)) for u in fleet],
                                EngineRandom(w, z))
                with contextlib.redirect_stdout(io.StringIO()):  # the engine prints a lot
                    assert engine_play(units, fleet, w, z) == expected


def test_the_easy_bots_are_beaten_more_often(monkeypatch, tmp_path):
    """A measurement of bot_empires' design, not of a number taken from it.

    What is measured: 81 random squads (3 to 5 recent units, players of level 10 to 90) fight the 15 bots that
    defense_fleet builds for them, 3 battles each, played by play() with the engine's random numbers
    (EngineRandom) from a fixed seed. play() is a copy of battle_engine's battle rules written in this test; it is
    not its own oracle: every 300th battle of this sample is played again by battle_engine.battle_complete_response
    itself and must end the same (test_the_battles_played_here_are_the_engines does the same for other squads).

    What is expected, from bot_empires' docstring, not from running it: the bots of the five steps
    (GlobalPVPPlayerDelta -2, -1, 0, +2, +4) are easier the lower the step, the bot of the player's level is
    "a nearly even match" (HANDICAP), so the easiest are beaten more than half the time and the hardest less.
    "Nearly even" is taken as within 8 points of half; with HANDICAP 0 (an exact mirror) the docstring has the
    player win about 38%, outside it. What the player wins depends mostly on the squads drawn, so the sample has
    many squads and few battles."""
    monkeypatch.setattr(battle_engine, "report_battle_log", lambda *a: None)
    rng = random.Random(7)
    wins, games = [0] * len(bot_empires.DELTAS), [0] * len(bot_empires.DELTAS)
    replayed = 0
    with app.test_request_context():
        session.sid = "0"
        for level in range(10, 100, 10):
            for _ in range(9):
                units = random_squad(rng, level)
                setup_session(monkeypatch, tmp_path, level=level, units=units)
                player = [(kind(u), strength(u)) for u in units]
                fleets = [[u.split(",")[0] for u in bot_empires.defense_fleet(bot)] for bot in bot_empires.bots()]
                for i, fleet in enumerate(fleets):
                    bot = [(kind(u), strength(u)) for u in fleet]
                    for _ in range(3):
                        w, z = rng.randrange(1, 2 ** 32), rng.randrange(1, 2 ** 32)
                        player_left, bot_left = play(player, bot, EngineRandom(w, z))
                        if sum(games) % 300 == 0:
                            with contextlib.redirect_stdout(io.StringIO()):  # the engine prints a lot
                                assert engine_play(units, fleet, w, z) == (player_left, bot_left)
                            replayed += 1
                        wins[i // 3] += sum(player_left) > sum(bot_left)
                        games[i // 3] += 1
    rates = [w / g for w, g in zip(wins, games)]
    print("player wins by step", [round(r, 2) for r in rates], "battles replayed by the engine", replayed)
    assert games == [81 * 9] * 5 and replayed == 13
    assert rates[0] > rates[1] > rates[2] > rates[3] > rates[4]
    assert abs(rates[2] - 0.5) <= 0.08
    assert rates[0] > 0.5 > rates[4]


def test_bot_saves_keep_invasions(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path)
        uid = bot_empires.bots()[3]["uid"]
        save = bot_empires.find_save(uid)
        assert save["bot"] and save["user_object"]["userInfo"]["world"]["objects"]
        save["user_object"]["pvp"]["invaders"]["u1"] = {"status": 1}
        bot_empires.store_save(save)
        assert bot_empires.find_save(str(uid))["user_object"]["pvp"]["invaders"] == {"u1": {"status": 1}}
        assert bot_empires.find_save(12345) is None


def test_a_write_cut_short_keeps_the_old_state(monkeypatch, tmp_path):
    with app.test_request_context():
        setup_session(monkeypatch, tmp_path)
        uid = bot_empires.bots()[3]["uid"]
        save = bot_empires.find_save(uid)
        save["user_object"]["pvp"]["invaders"]["u1"] = {"status": 1}
        bot_empires.store_save(save)

        def cut_short(state, f):
            f.write('{"%s": {"inva' % uid)
            raise OSError("disk full")
        monkeypatch.setattr(bot_empires.json, "dump", cut_short)
        save["user_object"]["pvp"]["invaders"]["u2"] = {"status": 1}
        # _write_state: "a write cut short leaves the old state"; it does not hide the error from the call
        with pytest.raises(OSError, match="disk full"):
            bot_empires.store_save(save)
        monkeypatch.undo()
        setup_session(monkeypatch, tmp_path)
        assert bot_empires.find_save(uid)["user_object"]["pvp"]["invaders"] == {"u1": {"status": 1}}


def test_winning_against_a_bot_without_its_state(monkeypatch, tmp_path):
    """The bot state file was removed during the battle: the win still counts, nothing breaks."""
    with app.test_request_context():
        session.sid = "0"
        setup_session(monkeypatch, tmp_path)
        uid = bot_empires.bots()[0]["uid"]
        battle_engine.invasion_complete(uid, {}, [battle_engine.lookup_item_by_code("U05")], [100])
        assert bot_empires.fight_list()["wins"] == 1
        zid = "u" + str(battle_engine.get_zid())
        save = bot_empires.find_save(uid)
        save["user_object"]["pvp"]["invaders"][zid] = {"status": 1}
        bot_empires.store_save(save)
        battle_engine.invasion_complete(uid, {}, [battle_engine.lookup_item_by_code("U05")], [100])
        assert bot_empires.find_save(uid)["user_object"]["pvp"]["invaders"][zid] == {"status": 2,
                                                                                    "attacker_fleet": ["U05,,,,"]}


def test_wins_count_for_the_day(monkeypatch, tmp_path):
    with app.test_request_context():
        user = setup_session(monkeypatch, tmp_path)
        bot_empires.battle_won(bot_empires.FIRST_UID)
        bot_empires.battle_won(12345)  # not a bot
        assert bot_empires.fight_list()["wins"] == 1
        user["userInfo"]["player"]["globalPVPBatch"]["ts"] -= bot_empires.FIGHT_LIST_DURATION
        assert bot_empires.fight_list()["wins"] == 0
