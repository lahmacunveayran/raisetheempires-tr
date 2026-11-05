"""The game settings the way the client reads them, for the battle tests to check the server against.

Read straight from the file the server sends the client (assets/29oct2012/gameSettings_with_fixes.xml) with
ElementTree, never through game_settings or battle_engine, and used the way the client's bytecode
(assets/ZGame.109338.swf, read with turkce/araclar/abc.py) uses it:
- CombatChain.init: a Chain for each kind of a <chain type>, with its great and poor lists.
- CombatChain.getHitValue: the Chain of the attacker (getChain: the first kind of the chain the unit hasType), no Chain
  is GOOD; Chain.getHitValue: POOR if the defender hasType one of poor, else GREAT if one of great, else GOOD.
- CombatChain constants POOR 0, GOOD 1, GREAT 2 (GetAttackingHitChance), m_hitValues from <combatHitValues>.
- UnitItem.getXmlStrength: unit strength="..." if there is one (strength and attack strength alike), else the first
  <strengths><entry> whose level is above the player level, its strength or its attackStrength.
- UnitItem.weak: weak="1".
- WorldUpgradeManager.getModifiedStrength: the research <modifier strength=".."> of an <item type="upgrade">.
- ConsumableItem.getBattleValue / againstList / affectsAll: the <consumable> attributes of a power, its <against>.
- UnitItem.getModifier: the mod of the first <against> whose type the unit hasType.
"""
import functools
import math
import os
import xml.etree.ElementTree as ET

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "29oct2012",
                    "gameSettings_with_fixes.xml")
CHANCE = {"poor": 0, "good": 1, "great": 2}  # CombatChain.POOR, GOOD, GREAT


@functools.lru_cache(maxsize=None)
def settings():
    root = ET.parse(PATH).getroot()
    chains = {}
    for chain in root.find("combatChain"):
        for kind in chain.get("type").split(","):
            chains[kind] = (chain.get("great", "").split(","), chain.get("poor", "").split(","))
    hit_values = {v.get("type"): (float(v.get("critical")), float(v.get("direct"))) for v in root.find("combatHitValues")}
    units = {}
    for item in root.iter("item"):
        unit = item.find("unit")
        if unit is None or not item.get("code"):
            continue
        strengths = unit.find("strengths")
        cost = item.find("cost")
        units[item.get("code")] = {
            "types": unit.get("type", "").split(","),
            "strength": unit.get("strength"),
            "entries": [(int(e.get("level")), int(e.get("strength")), int(e.get("attackStrength")))
                        for e in (strengths if strengths is not None else [])],
            "weak": unit.get("weak") == "1",
            "cost": list(cost.attrib) if cost is not None else [],  # in the order of the file, as resourceCosts
        }
    rewards = {hit.tag: [dict(r.attrib) for r in hit] for hit in root.find("combatRewards")}
    # research: <item type="upgrade" code="XA01"><modifier accuracy="10" percent="true"/> (UpgradeItem)
    upgrades = {item.get("code"): dict(item.find("modifier").attrib) for item in root.iter("item")
                if item.find("modifier") is not None and item.get("code")}
    # powers: <item code="N36"><consumable dot="15" type="all" ...><against type="infantry" mod="2.0"/> (ConsumableItem)
    consumables = {item.get("code"): (dict(item.find("consumable").attrib),
                                      [dict(a.attrib) for a in item.find("consumable").findall("against")])
                   for item in root.iter("item") if item.find("consumable") is not None and item.get("code")}
    return {"chains": chains, "hit_values": hit_values, "units": units, "rewards": rewards,
            "game": dict(root.find("gamesettings").attrib), "upgrades": upgrades, "consumables": consumables}


def unit(code):
    return settings()["units"][code]


def grade_of_types(attacker_types, defender_types):
    """CombatChain.getHitValue for units of these types. Two kinds of the attacker with a chain each are looked up
    in the order of a Dictionary, which this does not know: they must give the same grade."""
    grades = set()
    for kind in attacker_types:
        if kind in settings()["chains"]:
            great, poor = settings()["chains"][kind]
            grades.add("poor" if set(poor) & set(defender_types) else
                       "great" if set(great) & set(defender_types) else "good")
    assert len(grades) <= 1, ("the client's Dictionary order would decide", attacker_types, defender_types, grades)
    return grades.pop() if grades else "good"


def grade(attacker, defender):
    return grade_of_types(unit(attacker)["types"], unit(defender)["types"])


def chance(attacker, defender):  # CombatChain.GetAttackingHitChance
    return CHANCE[grade(attacker, defender)]


def hit_value(attacker, defender):  # CombatChain.GetAttackingHitValue: (critical, direct)
    return settings()["hit_values"][grade(attacker, defender)]


def _xml_strength(code, level, attack):
    u = unit(code)
    if u["strength"] is not None:
        return int(u["strength"])
    entry = next(e for e in u["entries"] if level < e[0])
    return entry[2] if attack else entry[1]


def modified_strength(strength_, research):
    """WorldUpgradeManager.getModifiedStrength: each strength upgrade adds s * mod / 100 (percent) or mod, then
    Math.round (halves up); the other upgrades leave it."""
    for code in research:
        modifier = upgrade(code)
        if "strength" in modifier:
            if modifier.get("percent"):
                strength_ = strength_ + strength_ * float(modifier["strength"]) / 100
            else:
                strength_ = strength_ + float(modifier["strength"])
            strength_ = math.floor(strength_ + 0.5)
    return strength_


def strength(code, level=1, research=()):  # UnitItem.getStrength: getXmlStrength, then getModifiedStrength
    return modified_strength(_xml_strength(code, level, False), research)


def attack_strength(code, level=1, research=()):  # UnitItem.getAttackStrength
    return modified_strength(_xml_strength(code, level, True), research)


def upgrade(code):  # the <modifier> of a research item
    return settings()["upgrades"][code]


def consumable(code):  # (the <consumable> attributes, its <against> list) of a power
    return settings()["consumables"][code]


def battle_value(code, name):  # ConsumableItem.getBattleValue: parseFloat of the attribute, 0 without it
    return float(consumable(code)[0].get(name, 0))


def affects_all(code):  # ConsumableItem.affectsAll: type="all"
    return consumable(code)[0].get("type") == "all"


def types(code):
    return unit(code)["types"]


def modifier(against, code):
    """UnitItem.getModifier: the mod of the first <against> whose type the unit hasType (any of its types), else 1."""
    return next((float(a["mod"]) for a in against if a["type"] in types(code)), 1.0)


def weak(code):
    return unit(code)["weak"]


def game_number(name):  # ZGlobal.gameSettings.getNumber: an attribute of <gamesettings>
    return float(settings()["game"][name])


def rewards(hit_type):  # <combatRewards><hit_type><reward .../>
    return settings()["rewards"][hit_type]
