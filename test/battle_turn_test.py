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


def cut_to_3(x):  # MathUtils.roundTo(x, 3): int(x * 1000) / 1000, int() cuts toward zero (also below zero)
    return int(x * 1000) / 1000


def hit_modifier(attacker_research=(), defender_research=(), to_hit=0.0):
    """BattleAI.getHitPercentModifier, which GetAttackingHitValue takes off both critical and direct when it is not 0:
    WorldUpgradeManager.getModifiedAccuracy of the attacker's research (each accuracy upgrade adds mod * 0.01, cut to
    3 digits), less getModifiedDodge of the defender's (no research of the game has dodge), plus the powers'
    Fleet.getToHitModifier * 0.01 (the attack of the attacker's fleet's powers on it, less the defend of the
    defender's); the miss bonus is off (combatEnableMissBonus="false"); then cut to 3 digits."""
    accuracy = 0
    for code in attacker_research:
        if "accuracy" in client.upgrade(code):
            accuracy = cut_to_3(accuracy + float(client.upgrade(code)["accuracy"]) * 0.01)
    dodge = 0
    for code in defender_research:
        if "dodge" in client.upgrade(code):
            dodge += cut_to_3(float(client.upgrade(code)["dodge"]) * 0.01)
    modifier = accuracy - dodge
    if to_hit != 0:
        modifier += to_hit * 0.01
    return cut_to_3(modifier)


def modified_damage(research, damage):
    """WorldUpgradeManager.getModifiedDamage: a percent damage upgrade adds damage * mod / 100 (cut to 3 digits), any
    other adds mod."""
    for code in research:
        modifier = client.upgrade(code)
        if "damage" in modifier:
            if modifier.get("percent"):
                damage = cut_to_3(damage + damage * float(modifier["damage"]) / 100)
            else:
                damage += float(modifier["damage"])
    return damage


def client_damage(attacker, defender, defender_left, r, level=1, attacker_research=(), defender_research=(),
                  to_hit=0.0, damage_bonus=0.0, ai=False, ai_can_critical=True):
    """BattleAI.GetAttackingDamage and BattleHost.resolveAttack (no weaker units: no unit of the game has weaker="1"):
    - the attacker's attack strength against what the defender has left, times the defender's attack strength / 100
      (GetDamageBase 25: combatDamageBase, the first tier increment is 0), strengths with their research;
    - Fleet.getDamageModifier (the damage of the attacker's powers less the shield of the defender's), not below 0;
    - the attacker's damage research (getModifiedDamage); damage and upgradeDamage (what the research added) cut to
      3 digits;
    - the hit chances less hit_modifier; a roll below direct is a glancing hit (combatGlancingBlowMultiplier; the AI
      glances too, combatAICanMiss="false"), from critical on a critical one (combatCriticalHitMultiplier) but never
      with the STRONG_ROLL nor for an AI that cannot critical; both multiplied;
    - Math.ceil of both; damage - upgradeDamage == 0 gives one more (a hit does at least 1 of its own); a hit of the
      player that would leave the enemy unit at 0 < strength <= 1 one more ("Incing damage to prevent 1 strength")."""
    critical, direct = client.hit_value(attacker, defender)
    modifier = hit_modifier(attacker_research, defender_research, to_hit)
    if modifier != 0:
        critical, direct = critical - modifier, direct - modifier
    attack = cut_to_3(client.attack_strength(attacker, level, attacker_research))  # GetAttackingStrengthAgainst
    left = cut_to_3(defender_left)
    damage = 25 * (3 * attack + left) / (3 * left + attack)
    damage = damage / 100 * client.attack_strength(defender, level, defender_research)
    if damage_bonus != 0:
        damage = max(damage + damage_bonus, 0)
    before_research = damage
    damage = modified_damage(attacker_research, damage)
    damage, upgrade_damage = cut_to_3(damage), cut_to_3(damage - before_research)
    if r < direct:
        multiplier = client.game_number("combatGlancingBlowMultiplier")
    elif r != STRONG_ROLL and (ai_can_critical or not ai) and r >= critical:
        multiplier = client.game_number("combatCriticalHitMultiplier")
    else:
        multiplier = 1
    damage, upgrade_damage = math.ceil(damage * multiplier), math.ceil(upgrade_damage * multiplier)
    if damage - upgrade_damage == 0:
        damage += 1
    if not ai and 0 < defender_left - damage <= 1:
        damage += 1
    return damage


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
                    enemy_left[d] = max(0, enemy_left[d] - client_damage(players[a], enemies[d], enemy_left[d], roll))
                else:
                    r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
                    d, a = client_ai(rand, enemies, enemy_left, players, player_left)
                    roll = client_roll(enemies[d], players[a], rand)
                    player_left[a] = max(0, player_left[a] - client_damage(enemies[d], players[a], player_left[a], roll,
                                                                           ai=True))
                turns += 1
                assert (r["playerUnit"], r["enemyUnit"], r["ur"]) == (a, d, roll)
                assert (r["ps"], r["es"]) == (player_left[a], enemy_left[d])
                assert r["seeds"] == {"w": rand.w, "z": rand.z}
                if not any(player_left) or not any(enemy_left):
                    assert session["battle"] is None  # handle_win / handle_loss closed it
                    break
                assert list(session["battle"][0]) == player_left and list(session["battle"][1]) == enemy_left
    assert turns > 300


# ships and aircraft (navy and air battles): attackship, fighters, a bomber
SEA_AIR_POOL = ["UJ01", "SL7", "SF1", "AU06", "U101"]
# land units with a pirate infantry (PU4, "infantry,land"), which the poison gas hits twice (<against type="infantry">)
LAND_POOL = POOL + ["PU4"]
RESEARCH = ["XD01", "XD02", "XA01", "XA02", "XS03", "XS04"]  # damage 25%, accuracy 10%, strength
# powers as assign_consumable_response puts them in the battle: (code, side); a power of type="all" affects the whole
# side (index None, ConsumableItem.affectsAll), any other the unit it was used on
POWERS = [("N02", "ally"), ("N06", "ally"), ("N08", "ally"), ("N09", "ally"),  # the player's buffs of type all
          ("N07", "enemy"), ("N12", "enemy"), ("N24", "enemy"), ("N36", "enemy"),  # the player's on the enemy
          ("N62", "ally"), ("N65", "ally"),  # the enemy's secondary abilities on a player unit
          ("N63", "enemy"), ("N02", "enemy"), ("N06", "enemy")]  # the enemy's buffs


def side_bonus(powers, side, unit, name):
    """Fleet.getModifier: the sum of the battle value of every power of that side's fleet that affectsAll or is on
    the unit."""
    return sum(client.battle_value(code, name) for code, s, index, _ in powers
               if s == side and (index is None or index == unit))


def client_dot(powers, side, units, left):
    """Battle.state_UpdateFleetConsumables after an attack: Fleet.triggerDOTConsumables of the attacking side's fleet;
    every power with a dot (in the order they were put on) hits each live unit it is on (all of them for affectsAll,
    percent 1: no roll) by Battle.onUnitDamageFromConsumable: dot * UnitItem.getModifier, an enemy unit not left at
    0 < strength <= 1."""
    for code, s, index, _ in powers:
        dot = client.battle_value(code, "dot")
        if s != side or not dot:
            continue
        for u in (range(len(units)) if index is None else [index]):
            if left[u] > 0:
                damage = dot * client.modifier(client.consumable(code)[1], units[u])
                if side == "enemy" and 0 < left[u] - damage <= 1:
                    damage += 1
                left[u] = max(0, left[u] - damage)


def test_turns_with_powers_research_ships_and_levels_follow_the_client(monkeypatch):
    """Whole battles as above with what the first test leaves out: research of the player's units (strength, damage,
    accuracy), powers on either side (accuracy, evasion, damage, shield, damage over time), players of level 10 and
    up (the AI's critical hits then come from the experiment empire_combataicancritical, which every save has at
    2 = ENABLED), navy and air battles. After every attack the damage over time of the attacking side's powers ticks;
    after the enemy's the powers' durations go down by one (Fleet.updateConsumables on BATTLE_SEQUENCE_COMPLETE with
    endTurn) and those at 0 are gone."""
    rng = random.Random(11)
    turns = dots = 0
    with app.test_request_context():
        for _ in range(40):
            pool = rng.choice([LAND_POOL, SEA_AIR_POOL])
            level = rng.choice([1, 9, 10, 25])
            players = [rng.choice(pool) for _ in range(rng.randint(1, 4))]
            enemies = [rng.choice(pool) for _ in range(rng.randint(1, 4))]
            user = setup(monkeypatch, players, enemies, level=level)
            # the same codes may be on both sides: the research is the player's only
            research = {code: rng.sample(RESEARCH, rng.randint(0, 3)) for code in sorted(set(players) | set(enemies))}
            user["userInfo"]["world"]["research"] = {code: r for code, r in research.items() if r}
            world = user["userInfo"]["world"]
            world["randSeedW"], world["randSeedZ"] = rng.randrange(1, 2 ** 32), rng.randrange(1, 2 ** 32)
            rand = ClientRandom(world["randSeedW"], world["randSeedZ"])
            ai_can_critical = (client.settings()["game"]["combatAICanCritical"] == "true" if level < 10
                               else user["experiments"]["empire_combataicancritical"] == 2)
            player_research = [research[c] for c in players]
            player_left = [client.strength(c, level, research[c]) for c in players]
            enemy_left = [client.strength(c, level) for c in enemies]
            battle_engine.init_battle(PARAMS)
            assert list(session["battle"][0]) == player_left and list(session["battle"][1]) == enemy_left
            powers = []
            for code, side in rng.sample(POWERS, rng.randint(0, 4)):
                index = None if client.affects_all(code) else rng.randrange(len(players if side == "ally" else enemies))
                powers.append([code, side, index, int(client.battle_value(code, "duration"))])
                session["battle"][2].append((item(code), (side, index), powers[-1][3]))
            for turn in range(60):
                if turn % 2 == 0:
                    a = rng.choice([i for i, s in enumerate(player_left) if s > 0])
                    d = rng.choice([i for i, s in enumerate(enemy_left) if s > 0])
                    r = battle_engine.battle_complete_response(dict(PARAMS, id=[a, d]))["data"]
                    roll = client_roll(players[a], enemies[d], rand)
                    enemy_left[d] = max(0, enemy_left[d] - client_damage(
                        players[a], enemies[d], enemy_left[d], roll, level, attacker_research=player_research[a],
                        to_hit=side_bonus(powers, "ally", a, "attack") - side_bonus(powers, "enemy", d, "defend"),
                        damage_bonus=side_bonus(powers, "ally", a, "damage") - side_bonus(powers, "enemy", d, "shield")))
                else:
                    r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
                    d, a = client_ai(rand, enemies, enemy_left, players, player_left)
                    roll = client_roll(enemies[d], players[a], rand)
                    player_left[a] = max(0, player_left[a] - client_damage(
                        enemies[d], players[a], player_left[a], roll, level, defender_research=player_research[a],
                        to_hit=side_bonus(powers, "enemy", d, "attack") - side_bonus(powers, "ally", a, "defend"),
                        damage_bonus=side_bonus(powers, "enemy", d, "damage") - side_bonus(powers, "ally", a, "shield"),
                        ai=True, ai_can_critical=ai_can_critical))
                turns += 1
                assert (r["playerUnit"], r["enemyUnit"], r["ur"]) == (a, d, roll)
                assert (r["ps"], r["es"]) == (player_left[a], enemy_left[d])
                assert r["seeds"] == {"w": rand.w, "z": rand.z}
                before = player_left + enemy_left
                if turn % 2 == 0:
                    client_dot(powers, "ally", players, player_left)
                else:
                    client_dot(powers, "enemy", enemies, enemy_left)
                    powers = [[c, s, i, n - 1] for c, s, i, n in powers if n - 1 > 0]
                dots += before != player_left + enemy_left
                if not any(player_left) or not any(enemy_left):
                    assert session["battle"] is None  # handle_win / handle_loss closed it
                    break
                assert list(session["battle"][0]) == player_left and list(session["battle"][1]) == enemy_left
                assert [(c["-code"], tuple(t), n) for c, t, n in session["battle"][2]] == \
                    [(c, (s, i), n) for c, s, i, n in powers]
    assert turns > 400 and dots > 20


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
        assert r["ps"] == 150 - 53 == 150 - client_damage("ML11", "V06", 150, direct, level=25, ai=True)


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


def test_a_hit_the_shield_takes_all_of_still_does_one(monkeypatch):
    """BattleAI.GetAttackingDamage takes the shield off and stops at 0 (Math.max(damage + modifier, 0)); then
    BattleHost.resolveAttack: Math.ceil(damage) - Math.ceil(upgradeDamage) == 0 adds 1, so no hit of the client does
    nothing. N30 (BuffHunkerDown, shield="15") on a U05 against a U01: 25 * (3 * 30 + 100) / (3 * 100 + 30) / 100 *
    100 = 14.39, less 15 is 0 (glancing or not): 1, for the player's hit and for the enemy's."""
    shield = client.battle_value("N30", "shield")
    with app.test_request_context():
        setup(monkeypatch, ["U01"], ["U05"])
        session["battle"] = ([30], [100], [(item("N30"), ("enemy", None), 5)], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)  # antitank on tank: poor, direct 0.75: a glancing hit
        count_reward_rolls(monkeypatch)
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        assert r["es"] == 100 - 1 == 100 - client_damage("U01", "U05", 100, 0.5, damage_bonus=-shield)
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        session["battle"] = ([100], [30], [(item("N30"), ("ally", None), 5)], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)
        r = battle_engine.battle_complete_response(dict(PARAMS))["data"]
        assert r["ps"] == 100 - 1 == 100 - client_damage("U01", "U05", 100, 0.5, ai=True, damage_bonus=-shield)


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


def test_a_stunned_support_unit_does_not_cast(monkeypatch):
    """BattleHost.state_UseSecondaryAbility leaves stunned units out (the engine's comment): UL31 (N68 at 10%) is
    stunned by the player's N64, so the first "AI" assign is SU06's, N64 at 20%: a roll of 0.15 casts."""
    with app.test_request_context():
        setup_invader(monkeypatch, ["UL31", "SU06", "U05"], strengths=[250, 225, 100])
        session["battle"][2].append((item("N64"), ("enemy", 0), 5))
        fixed_rolls(monkeypatch, 0.15)
        battle_engine.assign_consumable_response(AI_ASSIGN)
        assert casting()


def test_the_enemys_power_on_a_player_unit_hits_it_and_ends_the_enemy_turn(monkeypatch):
    """After the "AI" assign that casts, the client sends the power itself for the player unit it chose (the player's
    fleet name, the code, the unit): SU04's N62 (di 30, attack -99, 5 turns, target="enemy" from the enemy's side).
    Battle.onUnitDamageFromConsumable: 30 on the U05 (a player unit: no last point added); the power stays on that
    unit, and a secondary ability ends the enemy's turn (BattleHost.onContinueFromConsumable goes on with the
    sequence, endTurn): the durations go down by one, the cast marker is gone. The U05 then hits with
    hit_modifier(to_hit=-99): critical and direct 0.99 higher."""
    with app.test_request_context():
        setup_invader(monkeypatch, ["SU04", "U01"], strengths=[125, 30])
        fixed_rolls(monkeypatch, 0.15)  # N62 casts at 20%
        battle_engine.assign_consumable_response(AI_ASSIGN)
        assert casting()
        battle_engine.assign_consumable_response({"id": 1, "level": 0, "name": OWN, "fleet": None, "map": None,
                                                  "code": "N62"})
        assert list(session["battle"][0]) == [100, 100 - client.battle_value("N62", "di")]
        assert [(c["-code"], tuple(t), n) for c, t, n in session["battle"][2]] == \
            [("N62", ("ally", 1), client.battle_value("N62", "duration") - 1)]
        fixed_rolls(monkeypatch, 0.9)  # tank on antitank: great (critical 0.75, direct 0): now 1.74 and 0.99
        r = battle_engine.battle_complete_response(dict(AI_ATTACK, id=[1, 1]))["data"]
        # 25 * (3 * 100 + 30) / (3 * 30 + 100) / 100 * 30 = 13.03 (its attack strength, not what it has left), now
        # a glancing hit (0.9 < 0.99): 1.303, ceil 2
        assert r["es"] == 30 - client_damage("U05", "U01", 30, 0.9, to_hit=client.battle_value("N62", "attack")) \
            == 30 - 2


def test_the_poison_gas_hits_infantry_twice_and_leaves_no_enemy_at_one(monkeypatch):
    """The player's N36 (dot 15, type all, <against type="infantry" mod="2.0">) on the enemy side ticks after the
    enemy's attack (Battle.state_UpdateFleetConsumables, Fleet.triggerDOTConsumables of the enemy fleet) through
    Battle.onUnitDamageFromConsumable: PU4 ("infantry,land") takes 30, a U05 at 16 would be left at 1 and takes 16,
    a U05 at 40 takes 15; the dead U01 is skipped."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["PU4", "U05", "U05", "U01"])
        session["battle"] = ([100], [20, 16, 40, 0], [(item("N36"), ("enemy", None), 7)],
                             battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)
        battle_engine.battle_complete_response(dict(PARAMS))
        left = [20, 16, 40, 0]
        client_dot([["N36", "enemy", None, 7]], "enemy", ["PU4", "U05", "U05", "U01"], left)
        assert left == [0, 0, 40 - 15, 0] == list(session["battle"][1])


def test_the_enemys_damage_over_time_ticks_after_the_players_attack(monkeypatch):
    """SU05's N65 (dot 20, not type all) on the player's second unit ticks after the player's attack (the attacking
    side's fleet): 21 - 20 leaves 1, a player unit may keep it; the first unit is not touched."""
    with app.test_request_context():
        setup(monkeypatch, ["U05", "U05"], ["U05"])
        session["battle"] = ([100, 21], [100], [(item("N65"), ("ally", 1), 5)], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        assert list(session["battle"][0]) == [100, 1] and r["ps"] == 100


def test_collateral_damage_takes_the_first_against_the_unit_has(monkeypatch):
    """Battle.onUnitDamageFromConsumable multiplies the chipDamage (ChipDamageManager.getDamage: ceil(uniqueNumber *
    chipFactor * di / 100), 4 * 3 * 30 / 100 = 4 for two units) by UnitItem.getModifier, the same as the power's own
    damage: the mod of the first <against> whose type the unit has among all its types. A made-up unit of the types
    x, y, aircraft and a made-up N80 with <against aircraft 2.0> then <against y 3.0>: 4 * 2.0 = 8 (by its first two
    types only it would be y: 12; both: 24). As the power's target it takes 30 * 2.0 = 60."""
    made_up = {"-code": "XXA", "-name": "three kinds", "unit": {"-type": "x,y,aircraft", "-strength": "100"}}
    power = copy.deepcopy(item("N80"))
    power["consumable"]["against"] = [{"-type": "aircraft", "-mod": "2.0"}, {"-type": "y", "-mod": "3.0"}]
    against = [{"type": "aircraft", "mod": "2.0"}, {"type": "y", "mod": "3.0"}]
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05"])
        record_progress(monkeypatch)
        count_reward_rolls(monkeypatch)
        monkeypatch.setattr(client, "types", lambda code: made_up["unit"]["-type"].split(",") if code == "XXA"
                            else client.unit(code)["types"])
        chip = math.ceil(4 * client.battle_value("N80", "chipFactor") * client.battle_value("N80", "di") / 100)
        left = [100, 100]
        battle_engine.apply_consumable_direct_impact({}, power, 0, [item("U05"), made_up], left, {}, False, [])
        assert left == [100 - 30 * client.modifier(against, "U05"), 100 - chip * client.modifier(against, "XXA")] \
            == [70, 92]
        left = [100, 100]
        battle_engine.apply_consumable_direct_impact({}, power, 1, [item("U05"), made_up], left, {}, False, [])
        assert left == [100 - chip * client.modifier(against, "U05"), 100 - 30 * client.modifier(against, "XXA")] \
            == [96, 40]


def test_the_ally_power_target_roll_below_a_half_takes_the_first(monkeypatch):
    """Fleet.getRandomUnitIndexFromList: int(Math.round(randBetween(0, n - 1))) of the live units: 0.2 of two is 0."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05", "U05"])
        ally_powers(monkeypatch, ["N04"])
        fixed_rolls(monkeypatch, 0.2)
        battle_engine.assign_consumable_response(dict(ALLY_POWER))
        assert list(session["battle"][1]) == [40, 100]


def test_the_ally_power_on_the_last_live_unit_rolls_no_target(monkeypatch):
    """Fleet.getRandomUnitIndexFromList returns the only unit of a list of one without a random number: the roll
    picks the power (of two), and no other roll is made."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05", "U05"])
        session["battle"] = ([100], [0, 100], [], battle_engine.BattleContext())
        ally_powers(monkeypatch, ["N04", "N05"])
        rolls = []
        monkeypatch.setattr(battle_engine, "roll_random_float", lambda: rolls.append("float") or 0.2)
        monkeypatch.setattr(battle_engine, "roll_random_between", lambda a, b: rolls.append((a, b)) or a + (b - a) * 0.2)
        battle_engine.assign_consumable_response(dict(ALLY_POWER))
        assert rolls == [(0, 1)] and list(session["battle"][1]) == [0, 40]  # N04 (0.2 of two: the first)


def test_the_ally_heal_goes_to_a_damaged_unit(monkeypatch):
    """BattleAllyConsumable.createEffect: Fleet.getRandomLiveUnitIndexFromFleet(heals) takes the damaged live units
    (strength below getStrength) for a heal (ConsumableItem.heals: not targetsEnemy and di < 0), and of a list of one
    rolls nothing: N40 (di -500) heals the U05 at 50, not the full one, whatever the roll."""
    assert client.battle_value("N40", "di") < 0 and client.consumable("N40")[0].get("target") != "enemy"
    with app.test_request_context():
        setup(monkeypatch, ["U05", "U05"], ["U05"])
        session["battle"] = ([50, 100], [100], [], battle_engine.BattleContext())
        ally_powers(monkeypatch, ["N40"])
        fixed_rolls(monkeypatch, 0.9)
        target_rolls = []
        monkeypatch.setattr(battle_engine, "roll_random_between",
                            lambda a, b: target_rolls.append((a, b)) or a + (b - a) * 0.9)
        battle_engine.assign_consumable_response(dict(ALLY_POWER))
        assert list(session["battle"][0]) == [100, 100]
        assert target_rolls == [(0, 0)]  # only the choice of the one power; no target roll of one unit


def test_the_ally_heal_target_roll_below_a_half_takes_the_first(monkeypatch):
    with app.test_request_context():
        setup(monkeypatch, ["U05", "U05"], ["U05"])
        session["battle"] = ([50, 50], [100], [], battle_engine.BattleContext())
        ally_powers(monkeypatch, ["N40"])
        fixed_rolls(monkeypatch, 0.2)  # of two damaged player units: Math.round(0.2) = 0
        battle_engine.assign_consumable_response(dict(ALLY_POWER))
        assert list(session["battle"][0]) == [100, 50]




def test_a_titan_is_a_tank_to_the_combat_chain(monkeypatch):
    """Chain.getHitValue: POOR if the defender hasType one of the chain's poor kinds (all its kinds, UnitItem.hasType).
    PU4 (infantry: poor="...,tank,...") on ML11 ("mega_arm,tank,land,mega") is poor, though mega_arm, its first kind,
    is in none of infantry's lists; and the enemy picks its unit by it (BattleAI.findBestUnit)."""
    assert client.grade("PU4", "ML11") == "poor" and client.grade("PU4", "U05") == "poor"
    with app.test_request_context():
        setup(monkeypatch, ["PU4"], ["ML11"])
        assert battle_engine.get_hit_chance(item("PU4"), item("ML11")) == client.chance("PU4", "ML11") == 0
        assert battle_engine.get_hit_value(battle_engine.get_unit_types(item("PU4")),
                                           battle_engine.get_unit_types(item("ML11"))) == client.hit_value("PU4", "ML11")
        fixed_rolls(monkeypatch, 0.5)  # poor: direct 0.75, a glancing hit
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        assert r["es"] == client.strength("ML11") - client_damage("PU4", "ML11", client.strength("ML11"), 0.5)


def test_a_power_of_type_all_hits_every_live_enemy_once(monkeypatch):
    """The player's N36 (di 15, dot 15, type all, target enemy, <against type="infantry" mod="2.0">) used on the
    enemy fleet: Fleet.triggerConsumable of an affectsAll power hits each live unit of the side (dead ones are
    skipped) through Battle.onUnitDamageFromConsumable with di * UnitItem.getModifier: PU4 20 - 30 is dead, U05
    100 - 15; the dead U01 gets nothing (no damage counted for it). The power then stays on the whole side for its
    duration (7)."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["PU4", "U05", "U01"])
        user["userInfo"]["player"]["inventory"]["items"]["N36"] = 1
        session["battle"] = ([100], [20, 100, 0], [], battle_engine.BattleContext())
        progress = record_progress(monkeypatch)
        count_reward_rolls(monkeypatch)
        fixed_rolls(monkeypatch, 0.5)
        battle_engine.assign_consumable_response({"id": 0, "level": 0, "name": "fleet3_1", "fleet": None, "map": None,
                                                  "code": "N36"})
        di, against = client.battle_value("N36", "di"), client.consumable("N36")[1]
        assert list(session["battle"][1]) == [0, 100 - di * client.modifier(against, "U05"), 0] == [0, 85, 0]
        assert [p[0] for p in progress] == ["battleDamage", "battleKill", "battleDamage"]
        assert [p[3] for p in progress] == ["PU4", "PU4", "U05"]
        assert [(c["-code"], tuple(t), n) for c, t, n in session["battle"][2]] == \
            [("N36", ("enemy", None), client.battle_value("N36", "duration"))]


def test_an_enemy_power_of_type_all_rolls_its_percent_for_each_unit(monkeypatch):
    """UL31's N68 (di 75, type all, percent="80") on the player's fleet: Fleet.triggerConsumable rolls
    ZGameRandom.float() for each live unit of an affectsAll power whose percent is not 1 (ConsumableItem.percent
    80 / 100) and a roll above it misses (UNIT_MISS): rolls 0.5 and 0.9 hit the first U05 and miss the second."""
    with app.test_request_context():
        setup_invader(monkeypatch, ["UL31", "U05"], strengths=[250, 100])
        rolls = iter([0.05, 0.5, 0.9])  # the cast (10%), then one per player unit
        monkeypatch.setattr(battle_engine, "roll_random_float", lambda: next(rolls))
        monkeypatch.setattr(battle_engine, "roll_random_between", lambda a, b: a + (b - a) * next(rolls))
        battle_engine.assign_consumable_response(AI_ASSIGN)
        assert casting()
        battle_engine.assign_consumable_response({"id": 0, "level": 0, "name": OWN, "fleet": None, "map": None,
                                                  "code": "N68"})
        assert client.battle_value("N68", "percent") / 100 == 0.8
        assert list(session["battle"][0]) == [100 - client.battle_value("N68", "di"), 100]
        assert next(rolls, None) is None


def test_a_power_without_damage_leaves_the_shield(monkeypatch):
    """BattleHost.updateUnitHealth takes a shield (N75, givesAbility shield) only for a damage above 0: the player's
    N08 (attack 99, type all, di 0) on its own side leaves the shield of its U05."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U05"])
        user["userInfo"]["player"]["inventory"]["items"]["N08"] = 1
        session["battle"] = ([100], [100], [(item("N75"), ("ally", 0), 9999999)], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)
        battle_engine.assign_consumable_response({"id": 0, "level": 0, "name": "fleet2_1", "fleet": None, "map": None,
                                                  "code": "N08"})
        assert battle_engine.is_shielded(("ally", 0), session["battle"][2])
        assert [c["-code"] for c, t, n in session["battle"][2]] == ["N75", "N08"]

def test_a_glancing_hit_with_damage_research_glances_the_research_too(monkeypatch):
    """BattleAI.GetAttackingDamage gives upgradeDamage, what the research added (XD01: 25%), and BattleHost.resolveAttack
    multiplies it by the glancing multiplier too before Math.ceil(damage) - Math.ceil(upgradeDamage) == 0 adds 1:
    U01 on U01 (30): 25 * (3 * 30 + 30) / (3 * 30 + 30) / 100 * 30 = 7.5, 9.375 with the research, glancing
    0.9375 and 0.1875: ceil 1 - 1 == 0, so 2 (the research unglanced, ceil 1.875 = 2, would leave 1)."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U01"], ["U01"])
        user["userInfo"]["world"]["research"] = {"U01": ["XD01"]}
        fixed_rolls(monkeypatch, 0.1)  # antitank on antitank: direct 0.25, a glancing hit
        count_reward_rolls(monkeypatch)
        r = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))["data"]
        assert r["es"] == 30 - 2 == 30 - client_damage("U01", "U01", 30, 0.1, attacker_research=["XD01"])
