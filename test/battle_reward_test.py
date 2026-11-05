"""Battle rewards, quest progress and answer fields, checked against the client (assets/ZGame.109338.swf, read with
turkce/araclar/abc.py) and the game XML (assets/29oct2012/gameSettings_with_fixes.xml and questSettings_with_fixes.xml,
read here with ElementTree, never through game_settings or battle_engine).

The client's rules used here:
- EnemyUnit.playDamageXPReward: nothing for a hit without damage; a glancing hit has no coin loot; a direct hit and a
  criticalhit one coin loot, a criticalkill three, of getCoinAmount(hit unit's getAttackStrength, damage); a
  criticalhit has one rare loot, a criticalkill three, of getRareAmount(the same) and getRareType(attackerStrength).
- BattleUnit.getCoinAmount / getRareAmount / getOilAmount: int(Math.ceil(...)) of combatRewardCoinsMultiplier,
  combatRewardRareMultiplier, combatRewardOilMultiplier of <gamesettings>.
- PlayerUnit.playDamageXPReward: when an enemy hit with damage destroys a unit of the player, one coin loot of
  getCoinAmount(unitItem.getStrength(fleet), damage), one oil loot of getOilAmount(the same strength) and one loot
  of 1 of the first rare resource of unitItem.resourceCosts (the <cost> attributes in the order of the file).
- WorldResourceManager.rareResourceIndex: "nrareN" is the N-th rare resource from the player's own, "rare" (it does
  not start with "n") the player's own, as nrare0. The save keeps the player's rare resources in that order in
  world.resourceOrder (as quest_engine.do_rewards).
- UnitItem.getModifiedStrength: a unit of a campaign fleet has int(strength * strengthMultiplier) of the island
  (<island><strength code mult>), the unit of the player its research (WorldUpgradeManager.getModifiedStrength:
  each strength upgrade adds strength * mod / 100 if percent, else mod, then Math.round).
- ChipDamageManager.getDamage: Math.ceil(uniqueNumber(target, other) * chipFactor * di / 100).
- IslandItem.giveRewards(!inReplay) (StrategicMap.battleComplete): in a replay every reward but the items, each
  through RewardHelper.getMultipliedCount with PlayerCampaign.getRewardMultiplier and combatReplayRewardMinimum;
  the Liberty Bond only in the first win.
- PVPManager.onTransactionComplete: a truthy metadata.newPVE makes the client update a PVE invasion marker.
Quest progress (battleDamage, battleKill) is the server's alone (the client has no rule for it, UnitTestValidateQuests
only names them): a battleDamage task counts the damage of each hit on a unit its targetInfo matches, a battleKill
task one for each such unit destroyed.
"""
import copy
import functools
import json
import math
import os
import xml.etree.ElementTree as ET

import pytest
from flask import Flask, session

import battle_engine
import client_settings as client

app = Flask(__name__)
app.secret_key = 'test'

HERE = os.path.dirname(os.path.abspath(__file__))
XML_DIR = os.path.join(HERE, "..", "assets", "29oct2012")
with open(os.path.join(HERE, "init_user.json")) as f:
    INIT_USER = json.load(f)

PARAMS = {"fleet": "fleet2_1", "target": "fleet3_1", "map": None}
START = 7  # each rare resource the player has before: an assignment instead of an addition would show


# --- the game XML, as the client reads it --------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def items():
    root = ET.parse(os.path.join(XML_DIR, "gameSettings_with_fixes.xml")).getroot()
    return {i.get("code"): i for i in root.iter("item") if i.get("code")}


@functools.lru_cache(maxsize=None)
def quests():
    root = ET.parse(os.path.join(XML_DIR, "questSettings_with_fixes.xml")).getroot()
    return {q.get("name"): q for q in root.iter("quest")}


def tasks(quest):
    return quests()[quest].find("tasks").findall("task")


def task_index(quest, action, target_type):
    """The task of the quest with this action whose <targetInfo unitType> lists target_type."""
    [i] = [i for i, t in enumerate(tasks(quest)) if t.get("action") == action
           and target_type in t.find("targetInfo").get("unitType", "").split(",")]
    return i


def fight_baddies(task):
    """<task action="fight" item=...>: the enemy fleet item, its <baddie item> units in order."""
    return [b.get("item") for b in items()[task.get("item")].findall("baddie")]


def task_fleet(task):
    """<task><fleet U01="1" V61="1"/>: the units the quest gives the player, in the order of the file."""
    fleet = task.find("fleet")
    return [code for code, count in fleet.attrib.items() for _ in range(int(count))]


def island(map_code, index):
    return items()[map_code].findall("island")[index]


def island_strength(map_code, index, code):
    """UnitItem.getModifiedStrength of a campaign fleet: int(strength * the island's strengthMultiplier)."""
    mults = {s.get("code"): float(s.get("mult")) for s in island(map_code, index).findall("strength")}
    return int(client.strength(code) * mults.get(code, 1))


def consumable(code):
    c = items()[code].find("consumable")
    return dict(c.attrib), [dict(a.attrib) for a in c.findall("against")]


def power_damage(code, target_code):
    """The direct impact of a power on a unit: di, times the mod of its first <against> the unit has a type of."""
    attrib, against = consumable(code)
    damage = int(attrib["di"])
    for a in against:
        if a["type"] in client.unit(target_code)["types"]:
            return damage * float(a["mod"])
    return damage


def modifier_of(code):
    """<item code><modifier .../>: what a research item changes."""
    mod = items()[code].find("modifier")
    return dict(mod.attrib) if mod is not None else {}


def researched_strength(code, upgrades):
    """WorldUpgradeManager.getModifiedStrength of the player's unit with these research items."""
    strength = client.strength(code)
    for upgrade in upgrades:
        mod = modifier_of(upgrade)
        if mod.get("strength"):
            if mod.get("percent") == "true":
                strength = strength + strength * float(mod["strength"]) / 100
            else:
                strength = strength + float(mod["strength"])
            strength = math.floor(strength + 0.5)  # Math.round
    return strength


def number(name):
    return client.game_number(name)


def reward_xp(hit_type):
    [xp] = [int(r["count"]) for r in client.rewards(hit_type) if r["type"] == "xp"]
    return xp


def coin_amount(attack_strength, damage):  # BattleUnit.getCoinAmount
    return math.ceil(attack_strength * damage * number("combatRewardCoinsMultiplier"))


def rare_amount(attack_strength, damage):  # BattleUnit.getRareAmount
    return math.ceil(attack_strength * damage * number("combatRewardRareMultiplier"))


def oil_amount(strength):  # BattleUnit.getOilAmount
    return math.ceil(strength * number("combatRewardOilMultiplier"))


def rare_index(cost_name):  # WorldResourceManager.rareResourceIndex, from the player's own rare resource
    return 0 if not cost_name.startswith("n") else int(cost_name[len("nrare"):])


def first_rare(code):  # PlayerUnit.playDamageXPReward: the first rare resource of resourceCosts
    return next(c for c in client.unit(code)["cost"] if c == "rare" or c.startswith("nrare"))


# ChipDamageManager.uniqueNumber(target, other) by the number of live units of the side (n 1, 2, 3, 4, 5 are the
# branches at 37, 41, 45, 117 and 165 of its bytecode; more units get 0)
UNIQUE_NUMBER = {
    1: [[0]],
    2: [[0, 4], [4, 0]],
    3: [[0, 4, 3], [4, 0, 3], [3, 4, 0]],
    4: [[0, 4, 0, 0], [4, 0, 3, 0], [0, 4, 0, 3], [0, 0, 4, 0]],
    5: [[0, 4, 3, 0, 0], [4, 0, 3, 2, 0], [4, 3, 0, 2, 1], [0, 4, 3, 0, 2], [0, 0, 3, 4, 0]],
}


def chip_damage(code, live, target, other):
    """ChipDamageManager.getDamage of a power with chipFactor on the other live unit; live = number of live units."""
    attrib, _ = consumable(code)
    return math.ceil(UNIQUE_NUMBER[live][target][other] * int(attrib["chipFactor"]) * int(attrib["di"]) / 100)


def round_to_3(x):  # MathUtils.roundTo(x, ZGameRandom.ACCURACY 3)
    return math.floor(x * 1000) / 1000


def hit_damage(attack, defender_left, defender_attack, roll, critical, direct):
    """BattleAI.GetAttackingDamage and BattleHost.resolveAttack for units without research and powers: GetDamageBase
    25, cut to 3 digits, glancing below direct, critical from critical, then Math.ceil."""
    damage = round_to_3(25 * (3 * attack + defender_left) / (3 * defender_left + attack) / 100 * defender_attack)
    if roll < direct:
        damage *= number("combatGlancingBlowMultiplier")
    elif roll >= critical:
        damage *= number("combatCriticalHitMultiplier")
    return math.ceil(damage)


# --- the session ---------------------------------------------------------------------------------------------------

def setup(monkeypatch, player_codes, enemy_codes, battle=None, quest_names=(), level=1):
    monkeypatch.setattr(battle_engine, "report_battle_log", lambda *a: None)
    session.sid = "0"
    user = copy.deepcopy(INIT_USER)
    user["userInfo"]["player"]["level"] = level
    world = user["userInfo"]["world"]
    world["research"] = {}
    for resource in world["resourceOrder"]:
        world["resources"][resource] = START
    session["user_object"] = user
    session["quests"] = [{"name": q, "complete": False, "expired": False, "progress": [0] * len(tasks(q)),
                          "completedTasks": 0} for q in quest_names]
    session["fleets"] = {"fleet2_1": [c + ",,,," for c in player_codes],
                         "fleet3_1": [{"-" + c: "1"} for c in enemy_codes]}
    session["battle"] = battle
    return user


def item(code):
    return battle_engine.lookup_item_by_code(code)


def fixed_rolls(monkeypatch, value):
    monkeypatch.setattr(battle_engine, "roll_random_float", lambda: value)
    monkeypatch.setattr(battle_engine, "roll_random_between", lambda a, b: a + (b - a) * value)


def count_reward_rolls(monkeypatch, value=0.9):
    rolls = []
    monkeypatch.setattr(battle_engine, "roll_reward_random_float", lambda: rolls.append(1) or value)
    return rolls


def resources():
    return session["user_object"]["userInfo"]["world"]["resources"]


def player():
    return session["user_object"]["userInfo"]["player"]


def progress(quest):
    [q] = [q for q in session["quests"] if q["name"] == quest]
    return q["progress"]


def rares_after(gained):
    """The rare resources of the player: START each, plus gained {index in resourceOrder: amount}."""
    order = session["user_object"]["userInfo"]["world"]["resourceOrder"]
    return {r: START + gained.get(i, 0) for i, r in enumerate(order)}


def rares_now():
    order = session["user_object"]["userInfo"]["world"]["resourceOrder"]
    return {r: resources()[r] for r in order}


# --- hits of the player's units ------------------------------------------------------------------------------------

def test_a_glancing_hit_of_1_damage_pays_and_counts(monkeypatch):
    """A U01 hits a U01 (30 left) with a roll of 0: 25 * (90 + 30) / (90 + 30) / 100 * 30 = 7.5, glancing 0.75,
    ceil 1. A hit of 1 still has damage: the xp of <glancinghit>, one reward roll, no coin loot, and the 1 counts
    for the battleDamage task of QW192 (targetInfo unitType land)."""
    with app.test_request_context():
        setup(monkeypatch, ["U01"], ["U01"], quest_names=["QW192"])
        strength = client.strength("U01")
        critical, direct = client.hit_value("U01", "U01")
        fixed_rolls(monkeypatch, 0.0)
        rolls = count_reward_rolls(monkeypatch)
        damage = hit_damage(strength, strength, strength, 0.0, critical, direct)
        assert damage == 1
        coins, xp = resources()["coins"], player()["xp"]
        answer = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))
        assert answer["data"]["es"] == strength - damage
        assert player()["xp"] == xp + reward_xp("glancinghit") and resources()["coins"] == coins
        assert len(rolls) == 1  # DooberManager.getRandomRewards; <glancinghit> has no energy reward
        expected = [0] * len(tasks("QW192"))
        expected[task_index("QW192", "battleDamage", "land")] = damage
        assert progress("QW192") == expected
        assert not answer["metadata"].get("newPVE")  # no PVE invasion for the client to mark


def test_a_kill_counts_once_for_battleKill_and_its_damage_for_battleDamage(monkeypatch):
    """A U05 (tank) hits a U01 (antitank, 5 left): great (critical 0.75, direct 0), a roll of 0.5 is a direct hit of
    ceil(25 * (300 + 5) / (15 + 100) / 100 * 30, cut to 3 digits) = 20, the U01 is destroyed: a kill. QW212 counts one
    kill of a land unit, QW192 the 20 damage on land; their tasks for other targets do not move."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01", "U01"], quest_names=["QW212", "QW192"],
              battle=([100], [5, 30], [], battle_engine.BattleContext()))
        critical, direct = client.hit_value("U05", "U01")
        fixed_rolls(monkeypatch, 0.5)
        count_reward_rolls(monkeypatch)
        damage = hit_damage(client.attack_strength("U05"), 5, client.attack_strength("U01"), 0.5, critical, direct)
        assert damage == 20
        coins, xp = resources()["coins"], player()["xp"]
        answer = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0]))
        assert answer["data"]["es"] == 0
        assert resources()["coins"] == coins + coin_amount(client.attack_strength("U01"), damage)
        assert player()["xp"] == xp + reward_xp("kill")
        kills = [0] * len(tasks("QW212"))
        kills[task_index("QW212", "battleKill", "land")] = 1
        assert progress("QW212") == kills
        hurt = [0] * len(tasks("QW192"))
        hurt[task_index("QW192", "battleDamage", "land")] = damage
        assert progress("QW192") == hurt
        assert not answer["metadata"].get("newPVE")


def test_a_critical_hit_pays_rare_loot_of_attack_strength_times_damage(monkeypatch):
    """EnemyUnit.playDamageXPReward: getRareAmount(300, 40) = ceil(300 * 40 * 0.0001) = 2 for each rare loot (one for
    a criticalhit, three for a criticalkill), of getRareType(98) = nrare3. 300 is the attackStrength of an ML11 for a
    level 25 player (<strengths><entry>)."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["ML11"], level=25)
        count_reward_rolls(monkeypatch)  # 0.9: none of the energy rewards
        attack = client.attack_strength("ML11", 25)
        assert attack == 300
        amount = rare_amount(attack, 40)
        assert amount == 2
        battle_engine.doBattleRewards("criticalhit", attack, 40, 98)
        assert rares_now() == rares_after({98 % 5: amount})
        battle_engine.doBattleRewards("criticalkill", attack, 40, 98)
        assert rares_now() == rares_after({98 % 5: amount + 3 * amount})


# --- the loss loot -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["UB96", "PU5", "U05", "SK4"])  # the first rare of their cost: rare, nrare1..4
def test_losing_a_unit_pays_one_of_the_first_rare_of_its_cost(monkeypatch, code):
    """PlayerUnit.playDamageXPReward for a hit of 10 that destroys the unit: coins and oil of its strength and 1 of
    the first rare resource of its <cost>, the other rare resources do not change."""
    with app.test_request_context():
        setup(monkeypatch, [code], ["U01"])
        before = dict(resources())
        battle_engine.doLossRewards(item(code), 10)
        strength = client.strength(code)
        assert resources()["coins"] == before["coins"] + coin_amount(strength, 10)
        assert resources()["oil"] == before["oil"] + oil_amount(strength)
        assert rares_now() == rares_after({rare_index(first_rare(code)): 1})


def test_losing_a_unit_of_nrare0_pays_the_players_own_rare(monkeypatch):
    """No unit of gameSettings_with_fixes.xml costs nrare0 (a mod's could): rareResourceIndex makes it the player's
    own rare resource, as rare."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        unit = {"-code": "XX0", "-name": "nrare0 unit", "unit": {"-type": "tank,land", "-strength": "100"},
                "cost": {"-coins": "1", "-nrare0": "3"}}
        battle_engine.doLossRewards(unit, 10)
        assert rares_now() == rares_after({rare_index("nrare0"): 1})


def test_losing_a_researched_unit_pays_by_its_researched_strength(monkeypatch):
    """PlayerUnit.playDamageXPReward counts from unitItem.getStrength(fleet), with the player's research: a U05 with
    XS05 (strength +20 %) has round(100 + 100 * 20 / 100) = 120."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U01"])
        session["user_object"]["userInfo"]["world"]["research"] = {"U05": ["XS05"]}
        strength = researched_strength("U05", ["XS05"])
        assert strength == 120
        before = dict(resources())
        battle_engine.doLossRewards(item("U05"), 10)
        assert resources()["coins"] == before["coins"] + coin_amount(strength, 10)
        assert resources()["oil"] == before["oil"] + oil_amount(strength)
        assert rares_now() == rares_after({rare_index(first_rare("U05")): 1})


def test_an_enemy_hit_of_1_damage_that_destroys_a_unit_pays_the_loss_loot(monkeypatch):
    """The enemy U01 (antitank) hits the player's PA1 (bomber, 1 left): poor (critical 1.11, direct 0.75), a roll of
    0.5 is glancing, ceil(25 * (90 + 1) / (3 + 30) / 100 * 10 cut to 3 digits * 0.1) = 1. The PA1 is destroyed by
    a hit with damage: its loss loot (no rare resource in its cost)."""
    with app.test_request_context():
        setup(monkeypatch, ["PA1"], ["U01"], battle=([1], [30], [], battle_engine.BattleContext()))
        critical, direct = client.hit_value("U01", "PA1")
        fixed_rolls(monkeypatch, 0.5)
        damage = hit_damage(client.attack_strength("U01"), 1, client.attack_strength("PA1"), 0.5, critical, direct)
        assert damage == 1
        before = dict(resources())
        answer = battle_engine.battle_complete_response(dict(PARAMS))
        assert answer["data"]["ps"] == 0
        strength = client.strength("PA1")
        assert resources()["coins"] == before["coins"] + coin_amount(strength, damage)
        assert resources()["oil"] == before["oil"] + oil_amount(strength)
        assert rares_now() == rares_after({})


# --- powers --------------------------------------------------------------------------------------------------------

def test_a_power_kill_on_a_campaign_island_pays_by_the_islands_strength(monkeypatch):
    """Island 1 of C003 has <strength code="U44" mult="0.4">: the enemy U44 has int(50 * 0.4) = 20 (getAttackStrength
    of a campaign fleet). An air strike (N04, di 30, no <against> for ships) destroys it: getCoinAmount(20, 30)."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["U44"])
        user["userInfo"]["world"]["campaign"]["active"]["C003"] = {"status": 1 << 20, "fleets": []}
        count_reward_rolls(monkeypatch)
        strength = island_strength("C003", 1, "U44")
        assert strength == 20
        damage = power_damage("N04", "U44")
        left = [strength]
        coins, xp = resources()["coins"], player()["xp"]
        battle_engine.apply_consumable_direct_impact({}, item("N04"), 0, [item("U44")], left, {"map": "C003"},
                                                     False, [])
        assert left == [0]
        assert resources()["coins"] == coins + coin_amount(strength, damage)
        assert player()["xp"] == xp + reward_xp("kill")


def test_a_power_hit_of_1_damage_counts_for_battleDamage(monkeypatch):
    """A flak barrage (N80: di 30, chipFactor 3, against aircraft only) on the middle one of five U05 (tank, land):
    30 on it, ChipDamageManager.getDamage on the others, uniqueNumber(2, i) = 4, 3, 2, 1: 4, 3, 2 and 1. Each hit
    on a land unit counts for the battleDamage task of QW192, the hit of 1 too."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05"] * 5, quest_names=["QW192"])
        strength = client.strength("U05")
        left = [strength] * 5
        battle_engine.apply_consumable_direct_impact({}, item("N80"), 2, [item("U05")] * 5, left, {}, False, [])
        hits = [power_damage("N80", "U05") if i == 2 else chip_damage("N80", 5, 2, i) for i in range(5)]
        assert sorted(hits) == [1, 2, 3, 4, 30]
        assert left == [strength - h for h in hits]
        expected = [0] * len(tasks("QW192"))
        expected[task_index("QW192", "battleDamage", "land")] = sum(hits)
        assert progress("QW192") == expected


def test_a_power_that_does_no_damage_reports_no_quest_progress(monkeypatch):
    """An EMP (N11: disable stun, no di) on an enemy U05 does no damage: nothing counts for the battleDamage task of
    QW192 and the answer reports no quest."""
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05"], quest_names=["QW192"])
        assert "di" not in consumable("N11")[0]
        meta = {}
        left = [client.strength("U05")]
        battle_engine.apply_consumable_direct_impact(meta, item("N11"), 0, [item("U05")], left, {}, False, [])
        assert left == [client.strength("U05")]
        assert meta == {} and progress("QW192") == [0] * len(tasks("QW192"))


# --- replays -------------------------------------------------------------------------------------------------------

def campaign(user, statuses):
    user["userInfo"]["world"]["campaign"]["active"] = {m: {"status": i << 20, "fleets": []} for m, i in statuses.items()}


def replay_multiplier(lead_map, lead_island, map_code, index):
    """PlayerCampaign.getRewardMultiplier: span - min(lead island's globalIndex - this island's, span), times
    1 / span when above 0, else 0.01 (span: combatReplayRewardSpan)."""
    span = number("combatReplayRewardSpan")
    distance = int(island(lead_map, lead_island).get("globalIslandIndex")) - \
        int(island(map_code, index).get("globalIslandIndex"))
    factor = span - min(distance, span)
    return factor * (1 / span) if factor > 0 else 0.01


def replay_count(count, multiplier):
    """RewardHelper.getMultipliedCount with multiplierMinimum combatReplayRewardMinimum."""
    minimum = number("combatReplayRewardMinimum")
    return math.ceil(max(multiplier * count, minimum) if count > minimum else multiplier * count)


def island_rewards(map_code, index):
    return [dict(r.attrib) for r in island(map_code, index).findall("reward")]


def test_replaying_an_island_pays_its_rewards_times_the_replay_multiplier(monkeypatch):
    """Replay of island 0 of C003 (coins 100, xp 1) while the lead is island 1 of C004 (C000 and C003 are done):
    each reward times getRewardMultiplier, 100 is not above combatReplayRewardMinimum (100) so it is not raised to
    it. The last enemy (V61, 1 left) falls to a glancing hit of the U05 (tank on artillery: poor, roll 0.1): a kill
    without coins. No Liberty Bond and no next island in a replay."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U05"], ["V61"],
                     battle=([100], [1], [], battle_engine.BattleContext(map_name="C003", island=0, replaying=True)))
        campaign(user, {"C000": len(items()["C000"].findall("island")), "C003": len(items()["C003"].findall("island")),
                        "C004": 1})
        fixed_rolls(monkeypatch, 0.1)
        count_reward_rolls(monkeypatch)
        rewards = island_rewards("C003", 0)
        assert {r["type"]: r["count"] for r in rewards} == {"xp": "1", "coins": "100"}
        multiplier = replay_multiplier("C004", 1, "C003", 0)
        coins, xp = resources()["coins"], player()["xp"]
        bonds = player()["inventory"]["items"].get("xk01", 0)
        answer = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0], map="C003", index=0))
        assert answer["data"]["es"] == 0 and session["battle"] is None
        assert resources()["coins"] == coins + replay_count(100, multiplier)
        assert player()["xp"] == xp + reward_xp("kill") + replay_count(1, multiplier)
        assert player()["inventory"]["items"].get("xk01", 0) == bonds
        assert battle_engine.get_active_island_by_map("C003") == ("C003", len(items()["C003"].findall("island")))


def test_replaying_an_island_gives_no_items(monkeypatch):
    """Island 5 of C004 gives coins 1000 and a U21; in a replay (the lead is island 0 of C005) only the coins, raised
    to combatReplayRewardMinimum if the multiplier makes less of them. The last enemy (U43, 1 left) falls to a
    glancing hit of a U01 (antitank on attackship: poor, roll 0.1)."""
    with app.test_request_context():
        user = setup(monkeypatch, ["U01"], ["U43"],
                     battle=([30], [1], [], battle_engine.BattleContext(map_name="C004", island=5, replaying=True)))
        campaign(user, {m: len(items()[m].findall("island")) for m in ("C000", "C003", "C004")})
        fixed_rolls(monkeypatch, 0.1)
        count_reward_rolls(monkeypatch)
        rewards = island_rewards("C004", 5)
        [coins_reward] = [int(r["count"]) for r in rewards if r["type"] == "coins"]
        [item_code] = [r["item"] for r in rewards if r["type"] == "item"]
        multiplier = replay_multiplier("C005", 0, "C004", 5)
        coins = resources()["coins"]
        units = player()["inventory"]["items"].get(item_code, 0)
        answer = battle_engine.battle_complete_response(dict(PARAMS, id=[0, 0], map="C004", index=5))
        assert answer["data"]["es"] == 0
        assert resources()["coins"] == coins + replay_count(coins_reward, multiplier)
        assert player()["inventory"]["items"].get(item_code, 0) == units
