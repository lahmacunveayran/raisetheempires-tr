"""Oracle classification of every test function of test/ (denetim2). The judgments are the auditor's, made by reading
each test (the reason is given for the less obvious ones); the script only checks that every test function is
classified and counts them.

I1  expected value from an independent model of the client (bytecode, written out in the test) or from the XML,
    with the derivation in the test
I2  expected value follows from the test's own input or a stated rule (hand calculation, "what was put in comes out")
M   literal expected value without derivation (where it comes from is not stated; it may be the code's own output)
S   snapshot / golden master: compared with a file that holds the code's own earlier output
C   circular: the expected value is computed with the code under test (or a re-implementation written from it)
W   weak: can hardly fail (constant/config check, truthiness, conditional assertions on the code's own answer)
Usage: python oracle_siniflandirma.py <repo>
"""
import collections
import os
import re
import sys

I1, I2, M, S, C, W = "I1", "I2", "M", "S", "C", "W"
DEFAULT = {  # per file, the class of the tests not listed in EXCEPTIONS
    "battle_test.py": S, "battle_turn_test.py": I1, "bot_empires_test.py": I2, "bounty_center_test.py": M,
    "client_patches_test.py": I2, "empires_test.py": I2, "event_buildings_test.py": M, "megaseries_test.py": C,
    "quest_test.py": M, "quest_trees_test.py": I2, "save_actions_test.py": I2, "session_layer_test.py": I2,
    "slot_machine_test.py": I2, "state_machine_test.py": M, "titan_lab_test.py": I2, "treasure_vault_test.py": I2,
}
EXCEPTIONS = {
    # battle_test.py: init_battle tests compare with friendlies*.json / baddies*.json (dumps of item dicts) -> S
    "battle_test.py::test_assign_consumable_response_consumable": (M, "[120, 170, 150] without derivation"),
    "battle_test.py::test_assign_consumable_response_shrapnel": (M, "[116, 170, 147] without derivation"),
    "battle_test.py::test_assign_consumable_response_shrapnel_removed_dead": (M, "[116, 0, 120]"),
    "battle_test.py::test_assign_consumable_response_shrapnel_unit_dead": (M, "[116, 0, 147]"),
    "battle_test.py::test_spawn_fleet_initial_attack": (M, "pos '52,49', villain 'v18'"),
    "battle_test.py::test_spawn_fleet_quest_based": (M, ""),
    "battle_test.py::test_spawn_fleet_quest_odd_fleets": (M, ""),
    "battle_test.py::test_decode_unit_count_list": (I2, ""),
    "battle_test.py::test_encode_unit_string": (I2, ""),
    "battle_test.py::test_encode_unit_string_with_hp_shields": (I2, ""),
    "battle_test.py::test_encode_unit_strings": (I2, ""),
    "battle_test.py::test_decode_unit_string": (I2, ""),
    "battle_test.py::test_decode_unit_strings": (I2, ""),
    "battle_test.py::test_get_survival_player_fleet": (M, "whole fleet dict literal"),
    # battle_turn_test.py: client model (ClientRandom, client_ai, client_damage) or derivations in comments -> I1
    "battle_turn_test.py::test_all_stunned_player_units_do_not_stop_the_ai": (I2, "counts rolls"),
    "battle_turn_test.py::test_each_support_unit_rolls_its_own_cast_percent": (I2, "cast percents from the XML"),
    "battle_turn_test.py::test_killed_support_units_cast_no_more": (I2, ""),
    "battle_turn_test.py::test_the_next_enemy_turn_starts_with_the_first_support_unit": (I2, ""),
    "battle_turn_test.py::test_a_hit_that_does_no_damage_pays_nothing": (I2, ""),
    "battle_turn_test.py::test_losing_a_unit_pays_the_first_rare_of_its_cost": (I2, "made-up unit"),
    "battle_turn_test.py::test_a_killed_titan_controller_still_casts": (I2, "made-up unit"),
    # bot_empires_test.py
    "bot_empires_test.py::test_fight_list_follows_the_player_level_easy_ones_first": (M, "[83]*3 + [84]*3 ..."),
    "bot_empires_test.py::test_units_get_stronger_by_a_few_percent_a_level": (W, "range check of a constant"),
    "bot_empires_test.py::test_air_squads_meet_the_army_kinds_that_fare_alike": (I1, "combat chain"),
    "bot_empires_test.py::test_bot_units_have_their_animations": (I1, "the unit swf files"),
    "bot_empires_test.py::test_the_battles_played_here_are_the_engines": (C, "play() is written from battle_engine"),
    "bot_empires_test.py::test_the_easy_bots_are_beaten_more_often": (C, "bounds measured with the test's own model"),
    # bounty_center_test.py
    "bounty_center_test.py::test_bonds_only_while_active_against_close_players": (I2, ""),
    "bounty_center_test.py::test_bot_empires_pay_bonds": (I2, ""),
    # empires_test.py
    "empires_test.py::test_random_fleet_challenge_response": (M, "whole answer literal"),
    "empires_test.py::test_random_enemy_fleet_challenge_response": (M, "whole answer literal"),
    "empires_test.py::test_load_challenge_response": (M, "eFID 'pve', state 1"),
    "empires_test.py::test_tutorial_response": (M, "quest progress literal"),
    "empires_test.py::test_part_request_response": (M, "progress [4, 5, 0], B166: 4"),
    "empires_test.py::test_part_request_response_inventory_count": (M, "progress [2, 0, 1]"),
    "empires_test.py::test_load_survival_mode_response": (M, "whole answer literal"),
    "empires_test.py::test_init_user": (S, "init_user.json is the server's own new save"),
    "empires_test.py::test_session_cookie_is_same_site_strict": (W, "reads back a config value"),
    "empires_test.py::test_lookup_energy_cap_beyond_defined_levels": (M, "25, 46"),
    "empires_test.py::test_click_on_dormant_tree_is_ignored": (W, "passes if setState does nothing at all"),
    # event_buildings_test.py
    "event_buildings_test.py::test_events_match_their_items_and_quests": (I2, "module vs XML consistency"),
    "event_buildings_test.py::test_event_quests_are_not_unlocked_by_level": (I2, ""),
    "event_buildings_test.py::test_no_event_below_level_15": (I2, ""),
    "event_buildings_test.py::test_settings_carry_the_dates_and_working_assets": (I2, ""),
    "event_buildings_test.py::test_quest_settings_carry_the_dates_and_the_rewards_given": (I2, ""),
    # megaseries_test.py: expectations from megaseries.nodes / SERIES (the module's own reading of the XML) -> C
    "megaseries_test.py::test_playable_series_have_quests_and_entry_buildings": (W, "non-empty checks"),
    "megaseries_test.py::test_no_series_without_water_or_below_level": (I2, ""),
    # quest_trees_test.py
    "quest_trees_test.py::test_playable_trees_have_screens_and_quests": (W, "membership check"),
    "quest_trees_test.py::test_login_offers_one_tree_and_starts_its_first_quest": (C, "FIRST = quest_trees.first_quest"),
    "quest_trees_test.py::test_start_quest_tracks_node_and_activates_quest": (C, "quest_trees.nodes"),
    "quest_trees_test.py::test_finished_tree_makes_room_for_the_next": (C, "quest_trees.nodes / PLAYABLE"),
    "quest_trees_test.py::test_patch_settings_puts_free_spots_first": (C, "spots from hook_spots"),
    "quest_trees_test.py::test_login_remembers_spots_for_the_next_settings_request": (C, "== hook_spots(...)"),
    # session_layer_test.py
    "session_layer_test.py::test_every_state_machine_of_the_items_can_be_looked_up": (W, "no exception only"),
    # slot_machine_test.py
    "slot_machine_test.py::test_prizes_come_from_the_featured_set": (M, "20000 coins, EN6 ..."),
    "slot_machine_test.py::test_spin_with_tokens": (W, "if/else on the loot the code returned, unseeded random"),
    # state_machine_test.py
    "state_machine_test.py::test_a_backup_that_cannot_be_written_does_not_undo_the_level_up": (I2, "XML quoted"),
    # titan_lab_test.py
    "titan_lab_test.py::test_parts_and_counts": (M, "B281.. order, 10, 6"),
    "titan_lab_test.py::test_titan_battle_uses_the_titan_fleet": (M, "ML codes; all(strengths)"),
    "titan_lab_test.py::test_won_titan_battle_gives_the_part": (M, "B287: 3"),
    "titan_lab_test.py::test_titan_battle_won_by_the_last_hit": (I1, "derivation; roll via battle_engine.get_hit_value"),
    # treasure_vault_test.py
    "treasure_vault_test.py::test_players_past_level_26_get_the_vault_quest_once": (M, "Q140J, QB128"),
    "treasure_vault_test.py::test_open_with_keys": (W, "if/else on the loot the code returned, unseeded random"),
    "treasure_vault_test.py::test_open_with_cash": (M, "24 cash"),
    "treasure_vault_test.py::test_every_vault_can_give_each_of_its_prizes": (W, "unseeded random; 'res' off by one"),
}


def main(repo):
    tests = []
    for name in sorted(os.listdir(os.path.join(repo, "test"))):
        if name.endswith("_test.py"):
            with open(os.path.join(repo, "test", name), encoding="utf-8") as f:
                tests += [name + "::" + m for m in re.findall(r"^def (test_\w+)", f.read(), re.M)]
    unknown = [k for k in EXCEPTIONS if k not in tests]
    assert not unknown, unknown
    per_file = collections.defaultdict(collections.Counter)
    total = collections.Counter()
    for t in tests:
        cls = EXCEPTIONS.get(t, (DEFAULT[t.split("::")[0]], ""))[0]
        per_file[t.split("::")[0]][cls] += 1
        total[cls] += 1
    order = [I1, I2, M, S, C, W]
    print("%-26s %s" % ("file", "  ".join("%3s" % c for c in order)))
    for f in sorted(per_file):
        print("%-26s %s" % (f, "  ".join("%3d" % per_file[f][c] for c in order)))
    n = sum(total.values())
    print("%-26s %s   (%d test functions)" % ("TOTAL", "  ".join("%3d" % total[c] for c in order), n))
    print("share:", ", ".join("%s %.0f%%" % (c, 100 * total[c] / n) for c in order))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
