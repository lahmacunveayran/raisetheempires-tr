

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
        setup(monkeypatch, ["U05"], ["PU4", "U05", "U01"])
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
        setup(monkeypatch, ["U05"], ["U05"])
        session["battle"] = ([100], [100], [(item("N75"), ("ally", 0), 9999999)], battle_engine.BattleContext())
        fixed_rolls(monkeypatch, 0.5)
        battle_engine.assign_consumable_response({"id": 0, "level": 0, "name": "fleet2_1", "fleet": None, "map": None,
                                                  "code": "N08"})
        assert battle_engine.is_shielded(("ally", 0), session["battle"][2])
        assert [c["-code"] for c, t, n in session["battle"][2]] == ["N75", "N08"]
