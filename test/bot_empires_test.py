import copy
import glob
import json
import math
import os
import random
import sys

from flask import Flask, session

import battle_engine
import bot_empires

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRADES = bot_empires.GRADES
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


def test_units_get_stronger_by_a_few_percent_a_level():
    assert 1.03 < bot_empires.STRENGTH_PER_LEVEL < 1.06


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


def battle(player, bot, rng):
    """One battle with the rules of battle_engine.battle_complete_response: the player hits first, the sides take
    turns, the AI attacks as ai_best_attack does. The player picks the hit that takes the largest share of what the
    target has left. [(kind, strength)] each side; True if the player wins."""
    def roll():  # roll_random_float
        return math.floor(rng.random() * 1000) / 1000

    def grade(attacker, defender):  # get_hit_chance
        return GRADES[battle_engine.get_combat_chain_grade(attacker[0], defender[0])]

    def hit(attacker, defender, defender_left):
        critical, direct = battle_engine.get_hit_value(attacker[0], defender[0])
        damage = 25 * (3 * attacker[1] + defender_left) / (3 * defender_left + attacker[1]) / 100 * defender[1]
        damage = math.floor(damage * 1000) / 1000
        r = roll()
        damage *= 0.10 if r < direct else 1.5 if r >= critical else 1
        return math.ceil(damage)

    def expected(attacker, defender, defender_left):
        critical, direct = battle_engine.get_hit_value(attacker[0], defender[0])
        crit = max(0.0, 1 - critical)
        mean = direct * 0.1 + (1 - direct - crit) + crit * 1.5
        return mean * 25 * (3 * attacker[1] + defender_left) / (3 * defender_left + attacker[1]) / 100 * defender[1]

    def best_unit(units, left, other, r):  # ai_best_unit
        alive = [i for i in range(len(units)) if left[i] > 0]
        best = max([grade(units[i], other) for i in alive] + [-1])
        ties = [i for i in alive if grade(units[i], other) == best]
        return (ties[round(r * (len(ties) - 1))], best) if ties else (None, -1)

    def ai_attack():  # ai_best_attack: (bot unit, player unit)
        first = roll()
        method_1 = [best_unit(bot, bot_left, player[p], first) + (p,) for p in range(len(player)) if player_left[p] > 0]
        top = max(g for _, g, _ in method_1)
        pairs = [x for x in method_1 if x[1] == top and x[1] >= 0]
        if pairs:
            pick = pairs[round(roll() * (len(pairs) - 1)) if len(pairs) > 1 else 0]
            pairing_1 = (pairs[0][0],) + pick[1:]  # the engine's "bugged pairings"
        else:
            pairing_1 = None, 0, None
        method_2 = [best_unit(player, player_left, bot[b], first) + (b,) for b in range(len(bot)) if bot_left[b] > 0]
        top_2 = max(g for _, g, _ in method_2)
        threats = [p for p, g, _ in method_2 if g == top_2]
        pairing_2 = best_unit(bot, bot_left, player[threats[0]], roll()) + (threats[0],) if threats else (None, 0, None)
        ratio = pairing_2[1] / top if top > 0 else 0
        b, _, p = pairing_1 if (ratio < 0.5) ^ (roll() < 0.2) else pairing_2
        return b, p

    player_left, bot_left = [s for _, s in player], [s for _, s in bot]
    for turn in range(500):
        players = [i for i, s in enumerate(player_left) if s > 0]
        bots = [i for i, s in enumerate(bot_left) if s > 0]
        if not bots or not players:
            return bool(players)
        if turn % 2 == 0:
            a, d = max(((a, d) for a in players for d in bots),
                       key=lambda p: (min(1, expected(player[p[0]], bot[p[1]], bot_left[p[1]]) / bot_left[p[1]]),
                                      -bot_left[p[1]]))
            bot_left[d] -= hit(player[a], bot[d], bot_left[d])
            if bot_left[d] == 1:  # the engine does not leave an enemy at 1
                bot_left[d] = 0
        else:
            b, p = ai_attack()
            player_left[p] -= hit(bot[b], player[p], player_left[p])
    return sum(player_left) > sum(bot_left)


def test_the_easy_bots_are_beaten_more_often(monkeypatch, tmp_path):
    """Random squads of 3 to 5 recent units of players of level 10 to 90 against the bots of each step. Over 54
    squads of level 10 to 95 the player won about 58%, 54%, 49%, 39% and 33% of the battles against the five steps;
    these 18 squads vary more by the draw (over 13 seeds: 51-72%, 44-62% and 29-42%)."""
    rng = random.Random(7)
    wins, games = [0] * len(bot_empires.DELTAS), [0] * len(bot_empires.DELTAS)
    with app.test_request_context():
        for level in range(10, 100, 10):
            for _ in range(2):
                pool = [i["-code"] for i in bot_empires.DEFENDER_POOL if level - 20 <= int(i["requiredLevel"]) <= level]
                units = [rng.choice(pool) for _ in range(rng.randint(3, 5))]
                setup_session(monkeypatch, tmp_path, level=level, units=units)
                player = [(kind(u), strength(u)) for u in units]
                for i, bot in enumerate(bot_empires.bots()):
                    fleet = [(kind(u), strength(u)) for u in bot_empires.defense_fleet(bot)]
                    for _ in range(20):
                        wins[i // 3] += battle(player, fleet, rng)
                        games[i // 3] += 1
    rates = [w / g for w, g in zip(wins, games)]
    print("player wins by step", [round(r, 2) for r in rates])
    assert rates[0] > rates[2] > rates[4] and rates[0] - rates[4] >= 0.15
    assert 0.45 <= rates[0] <= 0.78 and 0.40 <= rates[2] <= 0.65 and 0.22 <= rates[4] <= 0.48


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


def test_wins_count_for_the_day(monkeypatch, tmp_path):
    with app.test_request_context():
        user = setup_session(monkeypatch, tmp_path)
        bot_empires.battle_won(bot_empires.FIRST_UID)
        bot_empires.battle_won(12345)  # not a bot
        assert bot_empires.fight_list()["wins"] == 1
        user["userInfo"]["player"]["globalPVPBatch"]["ts"] -= bot_empires.FIGHT_LIST_DURATION
        assert bot_empires.fight_list()["wins"] == 0
