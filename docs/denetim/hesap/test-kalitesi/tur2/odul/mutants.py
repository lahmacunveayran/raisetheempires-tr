"""The mutants of the odul brief, as single text changes of battle_engine.py at cb00c06.

mutmut ids (mutmut_A_survivors.txt) are kept; its line numbers are 3 lower than cb00c06 (the file grew 3 lines
before line 121 since that run). Extra ids D* are the B-O5 survivors of denetim2 (mut_battle_engine.json) and the
names/counts of the quest progress the brief names.
kind: "print" = only a print() argument changes (prints are neither in the answer nor in the save).
"""

PRINT_1452 = 'print("Combat loss rewards", unit["-code"], "coins:", math.ceil(strength * damage * 0.01), "oil:",'
PRINT_1453 = 'math.ceil(strength * 0.001), "rare" + str(rare) + ":", 1 if rare is not None else 0)'
RARES = '{"-rare": 0, "-nrare0": 0, "-nrare1": 1, "-nrare2": 2, "-nrare3": 3, "-nrare4": 4}'

MUTANTS = [
    # id, line (cb00c06), old text, new text, kind
    ("34", 124, "if damage > 0:", "if damage > 1:", ""),
    ("36", 136, "if damage > 0:", "if damage >= 0:", ""),
    ("37", 136, "if damage > 0:", "if damage > 1:", ""),
    ("128", 1135, "if damage <= 0:", "if damage < 0:", ""),
    ("129", 1135, "if damage <= 0:", "if damage <= 1:", ""),
    ("135", 1141, "get_unit_attack_strength(unit, False, params)", "get_unit_attack_strength(unit, True, params)", ""),
    ("168", 1395, "attack_strength * damage * 0.0001", "attack_strength / damage * 0.0001", ""),
    ("186", 1403, "xp = 0", "xp = 1", ""),
    ("187", 1403, "xp = 0", "xp = None", ""),
    ("215", 1415, "rare_amount *= math.ceil", "rare_amount = math.ceil", ""),
    ("221", 1443, "get_unit_max_strength(unit, True)", "get_unit_max_strength(unit, False)", ""),
    ("240", 1448, '"-rare": 0', '"XX-rareXX": 0', ""),
    ("241", 1448, '"-rare": 0', '"-rare": 1', ""),
    ("242", 1448, '"-nrare0": 0', '"XX-nrare0XX": 0', ""),
    ("243", 1448, '"-nrare0": 0', '"-nrare0": 1', ""),
    ("244", 1448, '"-nrare1": 1', '"XX-nrare1XX": 1', ""),
    ("245", 1448, '"-nrare1": 1', '"-nrare1": 2', ""),
    ("250", 1448, '"-nrare4": 4', '"XX-nrare4XX": 4', ""),
    ("258", 1451, "] += 1", "] = 1", ""),
    ("261", 1452, '"Combat loss rewards"', '"XXCombat loss rewardsXX"', "print"),
    ("263", 1452, '"coins:"', '"XXcoins:XX"', "print"),
    ("264", 1452, "strength * damage * 0.01", "strength / damage * 0.01", "print"),
    ("265", 1452, "strength * damage * 0.01", "strength * damage / 0.01", "print"),
    ("266", 1452, "strength * damage * 0.01", "strength * damage * 1.01", "print"),
    ("267", 1452, '"oil:"', '"XXoil:XX"', "print"),
    ("268", 1453, "strength * 0.001", "strength / 0.001", "print"),
    ("269", 1453, "strength * 0.001", "strength * 1.001", "print"),
    ("270", 1453, '"rare" + str', '"XXrareXX" + str', "print"),
    ("273", 1453, '+ ":"', '+ "XX:XX"', "print"),
    ("274", 1453, "1 if rare is not None else 0", "2 if rare is not None else 0", "print"),
    ("275", 1453, "1 if rare is not None else 0", "1 if rare is  None else 0", "print"),
    ("276", 1453, "1 if rare is not None else 0", "1 if rare is not None else 1", "print"),
    # B-O5 survivors of denetim2 and the quest progress of the brief
    ("D32a", 32, 'meta = {"newPVE": 0}', 'meta = {"XXnewPVEXX": 0}', ""),
    ("D32b", 32, 'meta = {"newPVE": 0}', 'meta = {"newPVE": 1}', ""),
    ("D121a", 121, '"battleKill", 1,', '"XXbattleKillXX", 1,', ""),
    ("D121b", 121, '"battleKill", 1,', '"battleKill", 2,', ""),
    ("D126a", 126, '"battleDamage", damage,', '"XXbattleDamageXX", damage,', ""),
    ("D126b", 126, '"battleDamage", damage,', '"battleDamage", damage + 1,', ""),
    ("D245", 245, "if a <= combat_replay_reward_minimum", "if a < combat_replay_reward_minimum", ""),
    ("D247", 247, "(lambda a: 0)", "(lambda a: None)", ""),
    ("D484", 484, 'e["complete"] == False]', 'e["complete"] == True]', ""),
    # targeted faults for the f2p evidence of the rewritten battle_test.py (B-Y3), not mutmut ids
    ("T473", 473, "for i in range(int(count))]", "for i in range(int(count) + 1)]", "target"),
    ("T503", 503, 'simple_list(enemy_fleet["baddie"])]', 'simple_list(enemy_fleet["baddie"])][1:]', "target"),
    ("T506", 506, "range(int(count))]", "range(int(count) + 1)]", "target"),
    ("T510", 510, "get_unit_max_strength(friendly, True)", "get_unit_max_strength(friendly, False)", "target"),
    ("T1464", 1464, "if handle_shield_upgrades(", "if not handle_shield_upgrades(", "target"),
    ("T1067", 1067, 'get("-di", 0))', 'get("-di", 0)) + 1', "target"),
    ("T1152", 1152, "return 4", "return 3", "target"),
    ("T1154", 1154, "[[0,4,3],[4,0,3],[3,4,0]]", "[[0,4,3],[3,0,4],[3,4,0]]", "target"),
    ("T1158", 1158, "[0,0,4,3,0]]", "[0,0,3,4,0]]", "fix"),
    # harness check only, not counted
    ("SANITY", 109, "damage = math.ceil(damage)", "damage = math.floor(damage)", "sanity"),
]
