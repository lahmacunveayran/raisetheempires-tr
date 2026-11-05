"""The battle turns themselves: what battle_complete_response, ai_best_attack, assign_consumable_response and the
rewards answer, checked against what the client computes (BattleAI, BattleUnit, EnemyUnit, PlayerUnit of
assets/ZGame.109338.swf). The client compares the units, the roll and the seeds of every answer with its own and
stops the battle with an error when they differ."""
import copy
import json
import math
import os
import random

from flask import Flask, session

import battle_engine
import client_settings as client

app = Flask(__name__)
app.secret_key = 'test'

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

PARAMS = {"fleet": "fleet2_1", "target": "fleet3_1", "map": None}


def setup(monkeypatch, player_codes, enemy_codes, battle=None, level=1):
    monkeypatch.setattr(battle_engine, "report_battle_log", lambda *a: None)
    session.sid = "0"
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    user["userInfo"]["world"]["research"] = {}
    session["user_object"] = user
    session["quests"] = []
    session["fleets"] = {"fleet2_1": [c + ",,,," for c in player_codes],
                         "fleet3_1": [{"-" + c: "1"} for c in enemy_codes]}
    session["battle"] = battle
    return user


def item(code):
    return battle_engine.lookup_item_by_code(code)


def fixed_rolls(monkeypatch, value):
    monkeypatch.setattr(battle_engine, "roll_random_float", lambda: value)
    monkeypatch.setattr(battle_engine, "roll_random_between", lambda a, b: a + (b - a) * value)


def resources():
    return session["user_object"]["userInfo"]["world"]["resources"]


# --- the client, written out from its bytecode --------------------------------------------------------------------

class ClientRandom:
    """ZGameRandom: two multiply-with-carry generators, floats cut to 3 digits (MathUtils.roundTo, ACCURACY 3)."""
    def __init__(self, w, z):
        self.w, self.z = w, z

    def float(self):
        self.z = 36969 * (self.z & 65535) + (self.z >> 16) & 0xFFFFFFFF
        self.w = 18000 * (self.w & 65535) + (self.w >> 16) & 0xFFFFFFFF
        return math.floor(((self.z << 16) + self.w & 0xFFFFFFFF) / 0xFFFFFFFF * 1000) / 1000


# the units, the combat chain and the hit values as the client reads them from gameSettings_with_fixes.xml
strength = client.strength
chance = client.chance


def client_round(x):  # Math.round: halves go up (ECMA-262), Math.round(0.5) is 1
    return math.floor(x + 0.5)


def round_to_3(x):  # MathUtils.roundTo(x, ZGameRandom.ACCURACY 3): int(x * 1000) / 1000
    return math.floor(x * 1000) / 1000


WEAK_ROLL, STRONG_ROLL = -2.0, 2.0  # BattleHost constants


def client_roll(attacker, defender, rand):
    """BattleHost.getDiceRoll: no random number when one of the units is weak."""
    return WEAK_ROLL if client.weak(attacker) else STRONG_ROLL if client.weak(defender) else rand.float()


def find_best_unit(units, left, other, r, stunned=()):
    """BattleAI.findBestUnit: the live, not stunned unit of units that hits other best, ties picked by r."""
    best, ties = -1, []
    for i, unit in enumerate(units):
        if left[i] > 0 and i not in stunned:
            value = chance(unit, other)
            if value > best:
                best, ties = value, [i]
            elif value >= 0 and value == best:
                ties.append(i)
    if not ties:
        return None, best
    return ties[client_round(r * (len(ties) - 1)) if len(ties) > 1 else 0], best


def client_ai(rand, enemies, enemy_left, players, player_left, stunned_players=()):
    """BattleAI.FindBestDefendingUnit: (enemy unit, player unit) the enemy attacks with and attacks."""
    r = rand.float()
    # FindBestDefendingUnitAgainstAttackers
    best, defender, attackers = -1, None, []
    for p, unit in enumerate(players):
        if player_left[p] > 0:
            d, value = find_best_unit(enemies, enemy_left, unit, r)
            if value > best:
                best, defender, attackers = value, d, [p]
            elif value >= 0 and value == best:
                attackers.append(p)
    basic = (defender, attackers[client_round(rand.float() * (len(attackers) - 1)) if len(attackers) > 1 else 0]
             if attackers else None)
    # FindBestDefendingUnitAgainstBestAttacker
    best_2, attacker = -1, None
    for e, unit in enumerate(enemies):
        if enemy_left[e] > 0:
            p, value = find_best_unit(players, player_left, unit, r, stunned_players)
            if value > best_2:
                best_2, attacker = value, p
    value_2, defender_2 = 0, None
    if attacker is not None:
        defender_2, value_2 = find_best_unit(enemies, enemy_left, players[attacker], rand.float())
    use_basic = (value_2 / best if best > 0 else 0) < 0.5  # m_switchRatio
    if rand.float() < 0.2:  # m_switchPercent
        use_basic = not use_basic
    return basic if use_basic else (defender_2, attacker)


def client_damage(attacker, defender, defender_left, r, level=1):
    """BattleAI.GetAttackingDamage and BattleHost.resolveAttack (no powers, no research, no weaker units):
    the attacker's attack strength against what the defender has left, times the defender's attack strength / 100
    (GetDamageBase 25: combatDamageBase, the first tier increment is 0), cut to 3 digits; a roll below direct is a
    glancing hit (combatGlancingBlowMultiplier), from critical on a critical one (combatCriticalHitMultiplier) but
    never with the STRONG_ROLL; then Math.ceil."""
    critical, direct = client.hit_value(attacker, defender)
    attack = client.attack_strength(attacker, level)
    damage = 25 * (3 * attack + defender_left) / (3 * defender_left + attack)
    damage = round_to_3(damage / 100 * client.attack_strength(defender, level))
    if r < direct:
        damage *= client.game_number("combatGlancingBlowMultiplier")
    elif r != STRONG_ROLL and r >= critical:
        damage *= client.game_number("combatCriticalHitMultiplier")
    return math.ceil(damage)


# --- turns --------------------------------------------------------------------------------------------------------

# army units: antitank, tank, artillery; a Titan arm (ML11: strength 1200, attackStrength 150 at level 1) and a weak
# pirate tank (PU3, weak="1": no roll)
POOL = ["U01", "U04", "U05", "V03", "V61", "V62", "ML11", "PU3"]


def test_turns_follow_the_client(monkeypatch):
    """Whole battles of random squads: every answer has the units, roll, strengths and seeds the client computes."""
    rng = random.Random(3)
    turns = 0
    with app.test_request_context():
        for _ in range(25):
            players = [rng.choice(POOL) for _ in range(rng.randint(1, 4))]
            enemies = [rng.choice(POOL) for _ in range(rng.randint(1, 4))]
            user = setup(monkeypatch, players, enemies)
            world = user["userInfo"]["world"]
            world["randSeedW"], world["randSeedZ"] = rng.randrange(1, 2 ** 32), rng.randrange(1, 2 ** 32)
            rand = ClientRandom(world["randSeedW"], world["randSeedZ"])
            player_left, enemy_left = [strength(c) for c in players], [strength(c) for c in enemies]
            for turn in range(60):
                if turn % 2 == 0:
                    a = rng.choice([i for i, s in enumerate(player_left) if s > 0])
                    d = rng.choice([i for i, s in enumerate(enemy_left) if s > 0])
                    r = battle_engine.battle_complete_response(dict(PARAMS, id=[a, d]))["data"]
                    roll = client_roll(players[a], enemies[d], rand)
                    enemy_left[d] -= client_damage(players[a], enemies[d], enemy_left[d], roll)
                    enemy_left[d] = 0 if enemy_left[d] <= 1 else enemy_left[d]  # not left at 1
                else:
                    r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
                    d, a = client_ai(rand, enemies, enemy_left, players, player_left)
                    roll = client_roll(enemies[d], players[a], rand)
                    player_left[a] = max(0, player_left[a] - client_damage(enemies[d], players[a], player_left[a], roll))
                turns += 1
                assert (r["playerUnit"], r["enemyUnit"], r["ur"]) == (a, d, roll)
                assert (r["ps"], r["es"]) == (player_left[a], enemy_left[d])
                assert r["seeds"] == {"w": rand.w, "z": rand.z}
                if not any(player_left) or not any(enemy_left):
                    assert session["battle"] is None  # handle_win / handle_loss closed it
                    break
                assert list(session["battle"][0]) == player_left and list(session["battle"][1]) == enemy_left
    assert turns > 300


def test_ai_turn_rolls_like_the_client(monkeypatch):
    """One unit a side: the first roll, the roll of the second method, the switch roll, then the hit."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U01"])
        world = user["userInfo"]["world"]
        rand = ClientRandom(world["randSeedW"], world["randSeedZ"])
        r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
        for _ in range(3):
            rand.float()
        roll = rand.float()
        assert r["ur"] == roll and r["seeds"] == {"w": rand.w, "z": rand.z}
        # antitank on tank is poor: below 0.75 a glancing hit, else a direct one
        assert r["ps"] == 100 - (2 if roll < 0.75 else 15)


def test_ai_attacks_the_most_dangerous_unit(monkeypatch):
    """The second method: the enemy goes for the player unit that hits it best, with the unit that hits that one
    best, unless the switch roll says otherwise."""
    with app.test_request_context():
        setup(monkeypatch, ["U01", "U05"], ["U04", "V62"])
        friendlies, friendly_strengths, baddies, baddie_strengths, consumables = battle_engine.init_battle(PARAMS)
        fixed_rolls(monkeypatch, 0.5)
        # method 1: U01 is hit greatly by U04 (tank), U05 greatly by V62 (artillery): two pairings, the roll of 0.5
        # picks U05 (Math.round), the enemy unit stays the first pairing's U04 (the client's own pairing)
        # method 2: U01 hits V62 greatly, the best of the player's against an enemy unit: the enemy goes for U01 with
        # its best unit against it, U04; the grades are alike (ratio 1) and 0.5 is no switch roll, so method 2
        enemy, grade, player = battle_engine.ai_best_attack(friendlies, friendly_strengths, baddies, baddie_strengths,
                                                            consumables)
        rand = type("R", (), {"float": lambda self: 0.5})()
        assert (enemy, player) == client_ai(rand, ["U04", "V62"], [50, 80], ["U01", "U05"], [30, 100]) == (0, 0)
        rolls = iter([0.5, 0.5, 0.5, 0.1])  # the switch roll last: method 1, U04 on U05
        monkeypatch.setattr(battle_engine, "roll_random_float", lambda: next(rolls))
        monkeypatch.setattr(battle_engine, "roll_random_between", lambda a, b: a + (b - a) * next(rolls))
        enemy, grade, player = battle_engine.ai_best_attack(friendlies, friendly_strengths, baddies, baddie_strengths,
                                                            consumables)
        client_rolls = iter([0.5, 0.5, 0.5, 0.1])
        rand = type("R", (), {"float": lambda self: next(client_rolls)})()
        assert (enemy, player) == client_ai(rand, ["U04", "V62"], [50, 80], ["U01", "U05"], [30, 100]) == (0, 1)


def test_all_stunned_player_units_do_not_stop_the_ai(monkeypatch):
    """Every player unit left is stunned (N64): the second method finds no attacker and rolls no second time."""
    with app.test_request_context():
        n64 = item("N64")
        setup(monkeypatch, ["U05", "U05"], ["US14", "U05"])
        stun = [(n64, ("ally", 0), 5)]
        session["battle"] = ([100, 0], [225, 100], stun, battle_engine.BattleContext())
        rolls = []
        monkeypatch.setattr(battle_engine, "roll_random_float", lambda: rolls.append(1) or 0.5)
        friendlies, friendly_strengths, baddies, baddie_strengths, consumables = battle_engine.init_battle(PARAMS)
        assert battle_engine.ai_best_attack(friendlies, friendly_strengths, baddies, baddie_strengths, consumables)[2] == 0
        assert len(rolls) == 2  # the first roll and the switch roll
        r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
        assert r["playerUnit"] == 0


def test_ties_are_broken_like_math_round():
    assert [battle_engine.as3_round(x) for x in (0.5, 1.5, 2.5, 0.499, 2.4)] == [1, 2, 3, 0, 2]
    with app.test_request_context():
        tanks = [item("U05"), item("U05")]
        # two tanks hit an antitank alike: a roll of 0.5 takes the second (Python's round() would take the first)
        assert battle_engine.ai_best_unit(tanks, [100, 100], item("U01"), 0.5, [], "enemy") == (1, 2)


def test_titans_hit_with_their_attack_strength(monkeypatch):
    """A Titan has strength (what it can take) and attackStrength (what it hits with and what a hit on it takes a
    share of): ML11 of a level 25 player 2400 and 300."""
    with app.test_request_context():
        setup(monkeypatch, ["V06"], ["ML11"], level=25)
        assert battle_engine.get_unit_attack_strength(item("ML11"), False) == 300
        assert battle_engine.get_unit_max_strength(item("ML11"), False) == 2400
        critical, direct = client.hit_value("V06", "ML11")  # antitank on mega_arm: poor, direct 0.75
        fixed_rolls(monkeypatch, direct)  # a direct hit
        coins = resources()["coins"]
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        # 25 * (3 * 150 + 2400) / (3 * 2400 + 150) = 9.69387..; / 100 * 300 = 29.0816.. cut to 29.081, ceil 30
        # (with its strength, 2400, instead of the attackStrength: 233)
        assert r["es"] == 2400 - 30 == 2400 - client_damage("V06", "ML11", 2400, direct, level=25)
        assert resources()["coins"] == coins + 90  # getCoinAmount of its attackStrength: ceil(300 * 30 * 0.01)
        critical, direct = client.hit_value("ML11", "V06")  # mega_arm on antitank: great, direct 0
        fixed_rolls(monkeypatch, direct)
        r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
        # 25 * (3 * 300 + 150) / (3 * 150 + 300) = 35; / 100 * 150 = 52.5, ceil 53 (97 with its strength 2400)
        assert r["ps"] == 150 - 53 == 150 - client_damage("ML11", "V06", 150, direct, level=25)


def test_research_strength_is_rounded():
    """WorldUpgradeManager.getModifiedStrength: Math.round(s + s * mod / 100) after each upgrade."""
    with app.test_request_context():
        session["user_object"] = copy.deepcopy(INIT_USER)
        session["user_object"]["userInfo"]["world"]["research"] = {"SK6": ["XS04"], "AU06": ["XS03"]}
        assert battle_engine.handle_strength_upgrades(90, item("SK6")) == 113  # 112.5
        assert battle_engine.handle_strength_upgrades(80, item("AU06")) == 106  # 106.4
        assert battle_engine.get_unit_max_strength(item("SK6"), True) == 113


def test_units_of_no_kind_in_the_chain_hit_good():
    """The NPC anti air (antiairland, antiairship) is not in combatChain: CombatChain.getHitValue gives GOOD."""
    with app.test_request_context():
        assert battle_engine.get_combat_chain_grade("antiairland", "tank") == "good"
        # <combatHitValues><value type="good" critical="0.99" direct="0.25"/>
        assert battle_engine.get_hit_value("antiairship", "fighter") == client.settings()["hit_values"]["good"] == \
            (0.99, 0.25)


# --- rewards ------------------------------------------------------------------------------------------------------

def count_reward_rolls(monkeypatch, value=0.1):
    rolls = []
    monkeypatch.setattr(battle_engine, "roll_reward_random_float", lambda: rolls.append(1) or value)
    return rolls


def test_hit_rewards_follow_the_client(monkeypatch):
    """EnemyUnit.playDamageXPReward: the reward random is rolled on every hit, then once for each energy reward;
    a glancing hit pays no coins, not even when it kills; the rare resource follows the attacker's strength now."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U01"])
        player = user["userInfo"]["player"]
        rolls = count_reward_rolls(monkeypatch)
        coins, xp = resources()["coins"], player["xp"]
        battle_engine.doBattleRewards("kill", 30, 3, 100, glancing=True)
        assert (resources()["coins"], player["xp"], len(rolls)) == (coins, xp + 1, 1)
        battle_engine.doBattleRewards("directhit", 30, 10, 100)
        assert (resources()["coins"], player["xp"], len(rolls)) == (coins + 3, xp + 2, 2)
        energy, iron = player["energy"], resources()["iron"]
        battle_engine.doBattleRewards("criticalkill", 300, 20, 98)  # 98 % 5 = 3: nrare3, the fourth of resourceOrder
        assert len(rolls) == 2 + 3 and player["energy"] == energy + 2  # rolls of 0.1 give both energy rewards
        assert resources()["coins"] == coins + 3 + 3 * math.ceil(300 * 20 * 0.01) and player["xp"] == xp + 5
        assert resources()["iron"] == iron + 3 * math.ceil(300 * 20 * 0.0001)


def test_mastery_rewards_roll_no_energy(monkeypatch):
    """With a mastery scalar other than 1 the client skips the energy rolls (addRewards) and spawnLoot scales the
    number of xp loots and each coin loot."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U01"])
        monkeypatch.setattr(battle_engine, "get_mastery_scalar", lambda: 1.5)
        rolls = count_reward_rolls(monkeypatch)
        coins, xp = resources()["coins"], user["userInfo"]["player"]["xp"]
        battle_engine.doBattleRewards("criticalkill", 30, 7, 100)
        assert len(rolls) == 1
        # getCoinAmount: ceil(30 * 7 * 0.01) = 3; spawnLoot: each of the 3 coin loots of a criticalkill is
        # Math.round(3 * 1.5) = Math.round(4.5) = 5 (halves up)
        assert resources()["coins"] == coins + 15
        assert user["userInfo"]["player"]["xp"] == xp + 5  # the 3 xp of a criticalkill: ceil(3 * 1.5)


def record_progress(monkeypatch):
    progress = []
    monkeypatch.setattr(battle_engine, "progress_battle_damage_count", lambda action, damage, ally, baddie:
                        progress.append((action, damage, ally.get("-code"), baddie["-code"])) or (lambda *a: False))
    return progress


def test_power_kills_pay_the_player(monkeypatch):
    """An air strike (N04, 30, twice on land) kills an enemy U01: the player gets the hit's coins and xp and the
    kill counts for the battleKill tasks, like a hit of a unit (BattleUnit.onUnitHit)."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U01", "U05"])
        user["userInfo"]["player"]["inventory"]["items"]["N04"] = 1
        progress = record_progress(monkeypatch)
        rolls = count_reward_rolls(monkeypatch)
        coins, xp = resources()["coins"], user["userInfo"]["player"]["xp"]
        battle_engine.assign_consumable_response({"id": 0, "level": 0, "name": "fleet3_1", "fleet": None, "map": None,
                                                  "code": "N04"})
        assert list(session["battle"][1]) == [0, 100]
        assert resources()["coins"] == coins + math.ceil(30 * 60 * 0.01) and user["userInfo"]["player"]["xp"] == xp + 1
        assert len(rolls) == 1
        assert progress == [("battleDamage", 60, None, "U01"), ("battleKill", 1, None, "U01")]


def test_losing_a_unit_to_a_power_pays_the_loss_loot(monkeypatch):
    """An enemy power kills the player's U05: no kill rewards, the client's loss loot (PlayerUnit.playDamageXPReward):
    coins for the hit, oil and one of the unit's first rare resource (nrare3)."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U01"])
        progress = record_progress(monkeypatch)
        before = dict(resources())
        xp = user["userInfo"]["player"]["xp"]
        left = [30]
        battle_engine.apply_consumable_direct_impact({}, item("N04"), 0, [item("U05")], left, {}, True, [])
        assert left == [0] and progress == [] and user["userInfo"]["player"]["xp"] == xp
        assert resources()["coins"] == before["coins"] + math.ceil(100 * 60 * 0.01)
        assert resources()["oil"] == before["oil"] + 1 and resources()["iron"] == before["iron"] + 1



def test_power_hits_that_do_not_kill_pay_nothing(monkeypatch):
    """Battle.onUnitDamageFromConsumable puts the damage in the hit event only for a dead unit (dead ? damage :
    false); without it EnemyUnit.playDamageXPReward gives nothing and rolls nothing. The damage still counts."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U05"])
        progress = record_progress(monkeypatch)
        rolls = count_reward_rolls(monkeypatch)
        coins, xp = resources()["coins"], user["userInfo"]["player"]["xp"]
        left = [100]
        battle_engine.apply_consumable_direct_impact({}, item("N04"), 0, [item("U05")], left, {}, False, [])
        assert left == [40] and resources()["coins"] == coins and user["userInfo"]["player"]["xp"] == xp
        assert rolls == [] and progress == [("battleDamage", 60, None, "U05")]


def test_a_power_kill_by_the_last_point_pays_for_it(monkeypatch):
    """60 damage would leave the U01 at 1: the client adds the 1 to the damage (Incing damage to prevent 1 strength)
    and counts the coins from 61."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        record_progress(monkeypatch)
        count_reward_rolls(monkeypatch)
        coins = resources()["coins"]
        left = [61]
        battle_engine.apply_consumable_direct_impact({}, item("N04"), 0, [item("U01")], left, {}, False, [])
        assert left == [0] and resources()["coins"] == coins + math.ceil(30 * 61 * 0.01)


# --- secondary abilities ------------------------------------------------------------------------------------------

ZID_FLEETS = ["fleet%d_2341959767162880" % i for i in range(1, 14, 2)]
OWN = "fleet14_2341959767162880"


def setup_invader(monkeypatch, enemy_codes, strengths=None):
    setup(monkeypatch, ["U05", "U05"], [])
    session["fleets"] = dict({name: None for name in ZID_FLEETS}, **{
        OWN: ["U05,100,0,0,0", "U05,100,0,1,0"],
        "FleetName": {"type": "army", "uid": "6709797546928099", "name": "FleetName", "status": 0,
                      "units": [c + ",,,," for c in enemy_codes], "invader": False}})
    if strengths:
        session["battle"] = ([100, 100], strengths, [], battle_engine.BattleContext())


AI_ASSIGN = {"id": 0, "level": 0, "name": "AI", "fleet": None, "map": None, "code": None}
AI_ATTACK = {"fleet": OWN, "target": "FleetName", "map": None}


def casting():
    return any(target[0] == "AI" for _, target, _ in session["battle"][2])


def test_each_support_unit_rolls_its_own_cast_percent(monkeypatch):
    """BattleHost.state_UseSecondaryAbility sends an "AI" assign for each support unit in turn: UL31 casts N68 at
    10%, SU06 N64 at 20%; a roll of 0.15 casts on the second assign only."""
    with app.test_request_context():
        setup_invader(monkeypatch, ["UL31", "SU06", "U05"])
        fixed_rolls(monkeypatch, 0.15)
        battle_engine.assign_consumable_response(AI_ASSIGN)
        assert not casting()
        battle_engine.assign_consumable_response(AI_ASSIGN)
        assert casting()


def test_killed_support_units_cast_no_more(monkeypatch):
    """A killed unit is out of the client's fleet: the first "AI" assign is the live SU06's."""
    with app.test_request_context():
        setup_invader(monkeypatch, ["UL31", "SU06", "U05"], strengths=[0, 210, 100])
        fixed_rolls(monkeypatch, 0.15)
        battle_engine.assign_consumable_response(AI_ASSIGN)
        assert casting()


def test_the_next_enemy_turn_starts_with_the_first_support_unit(monkeypatch):
    with app.test_request_context():
        setup_invader(monkeypatch, ["UL31", "SU06", "U05"])
        fixed_rolls(monkeypatch, 0.5)
        battle_engine.assign_consumable_response(AI_ASSIGN)
        battle_engine.assign_consumable_response(AI_ASSIGN)
        battle_engine.battle_complete_response(dict(AI_ATTACK))  # the enemy attacks: its turn is over
        assert session["battle"][2] == []
        fixed_rolls(monkeypatch, 0.05)
        battle_engine.assign_consumable_response(AI_ASSIGN)  # UL31 again, 0.05 < 10%
        assert casting()


# --- winning and losing -------------------------------------------------------------------------------------------

def test_losing_the_last_unit_ends_the_battle_with_the_loss_loot(monkeypatch):
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        session["battle"] = ([1], [30], [], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)  # antitank on tank, poor: a glancing hit of 7
        before = dict(resources())
        r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
        assert (r["playerUnit"], r["ps"], r["ur"]) == (0, 0, 0.5)
        assert session["battle"] is None
        assert resources()["coins"] == before["coins"] + 7 and resources()["oil"] == before["oil"] + 1
        assert resources()["iron"] == before["iron"] + 1


def test_winning_a_campaign_island(monkeypatch):
    """The last enemy unit of island 3 of C037 falls: the hit's and the island's rewards, a Liberty Bond, the next
    island opens and the battle is over."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U58", "SU02", "U63"])
        user["userInfo"]["world"]["campaign"]["active"]["C037"] = {"status": 2 << 20, "fleets": []}
        session["battle"] = ([100], [0, 0, 5], [], battle_engine.BattleContext(map_name="C037", island=2))
        critical, direct = client.hit_value("U05", "U63")
        fixed_rolls(monkeypatch, direct)  # a direct hit: a kill
        coins, xp = resources()["coins"], user["userInfo"]["player"]["xp"]
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 2], map="C037"))["data"]
        assert (r["playerUnit"], r["enemyUnit"], r["es"]) == (0, 2, 0)
        assert session["battle"] is None and list(session["last_battle"][1]) == [0, 0, 0]
        assert battle_engine.get_active_island_by_map("C037") == ("C037", 3)
        assert user["userInfo"]["player"]["inventory"]["items"].get("xk01") == 1
        damage = client_damage("U05", "U63", 5, direct)
        assert resources()["coins"] == coins + math.ceil(strength("U63") * damage * 0.01) + 3600
        assert user["userInfo"]["player"]["xp"] == xp + 1 + 1  # the kill and the island


# --- more of the client's rules ---------------------------------------------------------------------------------

def test_a_titan_of_the_player_hits_with_its_attack_strength(monkeypatch):
    """BattleAI.GetAttackingStrengthAgainst(attacker, defender, STRENGTH_MAX) is the attacker's getAttackStrength:
    ML11 of a level 25 player hits with 300, not with its strength 2400."""
    with app.test_request_context():
        setup(monkeypatch, ["ML11"], ["U05"], level=25)
        fixed_rolls(monkeypatch, 0.5)  # mega_arm on tank: good (critical 0.99, direct 0.25), a direct hit
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        # 25 * (3 * 300 + 100) / (3 * 100 + 300) = 41.666..; / 100 * 100 cut to 41.666, ceil 42 (68 with 2400)
        assert r["es"] == 100 - 42 == 100 - client_damage("ML11", "U05", 100, 0.5, level=25)


def test_a_hit_that_does_no_damage_pays_nothing(monkeypatch):
    """EnemyUnit.playDamageXPReward returns at once for a hit without damage: no reward roll, no xp."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U01"])
        shield = {"consumable": {"-shield": "100"}}  # takes all of the hit
        session["battle"] = ([100], [30], [(shield, ("enemy", 0), 5)], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)
        rolls = count_reward_rolls(monkeypatch)
        before, xp = dict(resources()), user["userInfo"]["player"]["xp"]
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        assert r["es"] == 30
        assert rolls == [] and user["userInfo"]["player"]["xp"] == xp and resources() == before


def test_a_glancing_hit_pays_no_coins(monkeypatch):
    """EnemyUnit.playDamageXPReward sets a coinAmount for a critical or a direct hit only, a glancing hit pays the
    xp of <combatRewards><glancinghit> (1)."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U01"], ["U05"])
        fixed_rolls(monkeypatch, 0.5)  # antitank on tank: poor, direct 0.75: 0.5 is a glancing hit
        count_reward_rolls(monkeypatch)
        coins, xp = resources()["coins"], user["userInfo"]["player"]["xp"]
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        # 25 * (3 * 30 + 100) / (3 * 100 + 30) / 100 * 100 = 14.393.., * 0.10, ceil 2
        assert r["es"] == 98 == 100 - client_damage("U01", "U05", 100, 0.5)
        assert resources()["coins"] == coins and user["userInfo"]["player"]["xp"] == xp + 1


def test_a_critical_hit_pays_a_rare_by_the_attackers_strength_left(monkeypatch):
    """EnemyUnit.playDamageXPReward: a criticalhit has one rare loot (numRareLoot 1) of getRareType(attackerStrength),
    "nrare" + strength % 5, where attackerStrength is the attacker's unit.strength now (BattleUnit.onUnitHit)."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        session["battle"] = ([98], [30], [], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.9)  # tank on antitank: great, critical 0.75: a critical hit
        count_reward_rolls(monkeypatch)
        before = dict(resources())
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        # 25 * (3 * 100 + 30) / (3 * 30 + 100) / 100 * 30 = 13.026.., * 1.5 = 19.539, ceil 20: 10 left, no kill
        assert r["es"] == 10 == 30 - client_damage("U05", "U01", 30, 0.9)
        # getRareAmount: ceil(30 * 20 * 0.0001) = 1; 98 % 5 = 3: nrare3, the fourth of resourceOrder (iron)
        assert resources()["iron"] == before["iron"] + 1 and resources()["aluminum"] == before["aluminum"]
        assert resources()["coins"] == before["coins"] + 6  # getCoinAmount: ceil(30 * 20 * 0.01)


def test_mastery_coins_are_rounded_like_math_round(monkeypatch):
    """spawnLoot: each coin loot is int(Math.round(coinAmount * scalar)); 3 * 1.1 = 3.3 gives 3 (ceil would be 4)."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        monkeypatch.setattr(battle_engine, "get_mastery_scalar", lambda: 1.1)
        count_reward_rolls(monkeypatch)
        coins = resources()["coins"]
        battle_engine.doBattleRewards("directhit", 30, 10, 100)  # getCoinAmount: ceil(30 * 10 * 0.01) = 3
        assert resources()["coins"] == coins + 3


def test_mastery_scales_the_rare_loot(monkeypatch):
    """spawnLoot: numRareLoot = int(Math.ceil(numRareLoot * scalar)); a criticalhit's 1 rare at 1.5 is 2 loots."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        monkeypatch.setattr(battle_engine, "get_mastery_scalar", lambda: 1.5)  # campaignMasteryScalars 1,1.5,2
        count_reward_rolls(monkeypatch)
        iron = resources()["iron"]
        battle_engine.doBattleRewards("criticalhit", 300, 20, 98)  # getRareAmount: ceil(300 * 20 * 0.0001) = 1
        assert resources()["iron"] == iron + 2  # 98 % 5 = 3: nrare3


def test_an_energy_roll_equal_to_the_percent_gives_the_energy(monkeypatch):
    """BattleUnit.shouldGiveReward: rewardInstance.float() <= percent gives it; <criticalhit> has an energy reward of
    1 at percent .25, a roll of exactly 0.25 (3 digits, ZGameRandom) gives it."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U01"])
        rolls = count_reward_rolls(monkeypatch, value=0.25)
        energy = user["userInfo"]["player"]["energy"]
        battle_engine.doBattleRewards("criticalhit", 30, 10, 100)
        assert len(rolls) == 2  # getRandomRewards, then the energy reward
        assert user["userInfo"]["player"]["energy"] == energy + 1


def test_losing_a_titan_pays_its_oil(monkeypatch):
    """PlayerUnit.playDamageXPReward: getOilAmount(getStrength) = ceil(2400 * combatRewardOilMultiplier 0.001) = 3
    for ML11 of a level 25 player, coins ceil(2400 * 100 * 0.01); its cost has no rare resource."""
    with app.test_request_context():
        setup(monkeypatch, ["ML11"], ["U01"], level=25)
        before = dict(resources())
        battle_engine.doLossRewards(item("ML11"), 100)
        assert resources()["oil"] == before["oil"] + 3 and resources()["coins"] == before["coins"] + 2400
        assert [r for r in ("aluminum", "copper", "gold", "iron", "uranium") if resources()[r] != before[r]] == []


def test_losing_a_unit_pays_the_first_rare_of_its_cost(monkeypatch):
    """PlayerUnit.playDamageXPReward takes the first rare resource of unitItem.resourceCosts, which lists the
    <cost> attributes in the order of the file (GameItem.resourceCosts). No unit of the game costs two rare
    resources, so a made up one."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        unit = {"-code": "XX1", "-name": "two rares", "unit": {"-type": "tank,land", "-strength": "100"},
                "cost": {"-coins": "1", "-nrare2": "3", "-nrare4": "1"}}
        before = dict(resources())
        battle_engine.doLossRewards(unit, 10)
        assert resources()["gold"] == before["gold"] + 1  # nrare2, the third of resourceOrder
        assert resources()["uranium"] == before["uranium"]


def test_a_power_kill_of_a_titan_pays_by_its_attack_strength(monkeypatch):
    """EnemyUnit.playDamageXPReward counts the coins from the hit unit's getAttackStrength: N76 (500) kills the ML11
    of a level 1 player (strength 1200, attackStrength 150): ceil(150 * 500 * 0.01) = 750."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["ML11"])
        count_reward_rolls(monkeypatch)
        coins = resources()["coins"]
        left = [400]
        battle_engine.apply_consumable_direct_impact({}, item("N76"), 0, [item("ML11")], left, {}, False, [])
        assert left == [0] and resources()["coins"] == coins + 750


def test_a_power_against_land_also_hits_a_titan_harder(monkeypatch):
    """The client takes a power's <against> modifier with UnitItem.getModifier: the first <against> whose type the
    unit has among all its types (UnitItem.hasType, m_types.indexOf). N04 (di 30) has <against type="land"
    mod="2.0">; ML11 is "mega_arm,tank,land,mega", so the client hits it for 30 * 2.0 = 60, like a U05 ("tank,land")."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["ML11", "U05"])
        count_reward_rolls(monkeypatch)
        left = [400, 100]
        battle_engine.apply_consumable_direct_impact({}, item("N04"), 0, [item("ML11"), item("U05")], left, {}, False,
                                                     [])
        battle_engine.apply_consumable_direct_impact({}, item("N04"), 1, [item("ML11"), item("U05")], left, {}, False,
                                                     [])
        assert left == [400 - 60, 100 - 60]


def test_only_the_first_matching_against_of_a_power_counts(monkeypatch):
    """UnitItem.getModifier stops at the first <against> the unit has (it jumps out of the loop), it does not
    multiply them. No power of the game has two, so this one is made up: land 2.0 then tank 3.0 on a U05
    ("tank,land") hits for 30 * 2.0 = 60, not 30 * 2.0 * 3.0 = 180."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05"])
        count_reward_rolls(monkeypatch)
        power = copy.deepcopy(item("N04"))
        power["consumable"]["against"] = [{"-type": "land", "-mod": "2.0"}, {"-type": "tank", "-mod": "3.0"}]
        left = [100]
        battle_engine.apply_consumable_direct_impact({}, power, 0, [item("U05")], left, {}, False, [])
        assert left == [100 - 60]


def test_collateral_damage_that_would_leave_1_takes_the_last_point(monkeypatch):
    """N80 (di 30, chipFactor 3) on the first of two enemy units: ChipDamageManager.getDamage gives the other
    ceil(4 * 3 * 30 / 100) = 4 (4 for two units); it has 5, so 1 would be left and the client adds it
    (Battle.onUnitDamageFromConsumable "Incing damage to prevent 1 strength"): a kill by 5."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01", "U05"])
        record_progress(monkeypatch)
        count_reward_rolls(monkeypatch)
        coins = resources()["coins"]
        left = [30, 5]
        battle_engine.apply_consumable_direct_impact({}, item("N80"), 0, [item("U01"), item("U05")], left, {}, False,
                                                     [])
        assert left == [0, 0]
        # kills of the target (ceil(30 * 30 * 0.01) = 9) and of the other (ceil(100 * 5 * 0.01) = 5)
        assert resources()["coins"] == coins + 9 + 5


def test_a_power_pays_the_unit_it_killed_once(monkeypatch):
    """The target killed by N80 is not paid again for its own collateral damage (there is none for it, 0)."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01", "U05"])
        progress = record_progress(monkeypatch)
        rolls = count_reward_rolls(monkeypatch)
        coins = resources()["coins"]
        left = [30, 100]
        battle_engine.apply_consumable_direct_impact({}, item("N80"), 0, [item("U01"), item("U05")], left, {}, False,
                                                     [])
        assert left == [0, 96]  # the other takes ceil(4 * 3 * 30 / 100) = 4
        assert resources()["coins"] == coins + 9 and len(rolls) == 1
        assert progress == [("battleDamage", 30, None, "U01"), ("battleKill", 1, None, "U01"),
                            ("battleDamage", 4, None, "U05")]


ALLY_POWER = {"code": "A0A", "name": "-1", "fleet": "fleet2_1", "target": "fleet3_1", "map": None, "level": 0}


def ally_powers(monkeypatch, codes):
    monkeypatch.setattr(battle_engine, "lookup_items_by_type_and_subtype", lambda *a: [item(c) for c in codes])


def test_the_ally_power_roll_of_a_half_takes_the_second(monkeypatch):
    """int(Math.round(r * (n - 1))) of two powers with r * 1 = 0.5 is 1 (Math.round goes up): N05, 30 on the land
    unit (N04 would be 60, twice on land)."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05"])
        ally_powers(monkeypatch, ["N04", "N05"])  # Steele's level is the player's + 5: 6, N05 needs 6
        fixed_rolls(monkeypatch, 0.5)
        battle_engine.assign_consumable_response(dict(ALLY_POWER))
        assert list(session["battle"][1]) == [70]


def test_the_ally_power_target_roll_of_a_half_takes_the_second(monkeypatch):
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05", "U05"])
        ally_powers(monkeypatch, ["N04"])
        fixed_rolls(monkeypatch, 0.5)  # of two live enemy units: Math.round(0.5) = 1
        battle_engine.assign_consumable_response(dict(ALLY_POWER))
        assert list(session["battle"][1]) == [100, 40]


def test_the_ally_heal_target_roll_of_a_half_takes_the_second(monkeypatch):
    with app.test_request_context():
        setup(monkeypatch, ["U05", "U05"], ["U05"])
        session["battle"] = ([50, 50], [100], [], battle_engine.BattleContext())
        ally_powers(monkeypatch, ["N40"])  # a heal of 500 for one unit, up to its strength
        fixed_rolls(monkeypatch, 0.5)  # of two live player units: Math.round(0.5) = 1
        battle_engine.assign_consumable_response(dict(ALLY_POWER))
        assert list(session["battle"][0]) == [50, 100]


def test_a_killed_titan_controller_still_casts(monkeypatch):
    """BattleHost.state_UseSecondaryAbility (the engine's comment): killed units are taken out of the enemy fleet,
    Titan controllers stay. No controller of the game has a secondary ability, so a torso (ML01) with N64's."""
    lookup = battle_engine.lookup_item_by_code

    def with_casting_torso(code):
        if code != "MLX":
            return lookup(code)
        torso = copy.deepcopy(lookup("ML01"))
        torso["-code"], torso["unit"]["-secondary"] = "MLX", "N64"
        return torso
    with app.test_request_context():
        monkeypatch.setattr(battle_engine, "lookup_item_by_code", with_casting_torso)
        setup_invader(monkeypatch, ["MLX", "U05"], strengths=[0, 100])
        fixed_rolls(monkeypatch, 0.15)  # N64 casts at 20%
        battle_engine.assign_consumable_response(AI_ASSIGN)
        assert casting()
