"""Fail-to-pass evidence for test/server_handlers_test.py: each mutant is put into one line of the production code
(bytes, the line's own ending kept), the tests that guard it are run with a timeout, the file is restored.
Run from the worktree root: python f2p_harness.py <launcher> <out.jsonl>"""
import json
import os
import subprocess
import sys
import time

T = "test/server_handlers_test.py::"
S = "empires-server.py"

# (file, line, old part of the line, new part, description, tests that must fail)
MUTANTS = [
    (S, 2722, b"get_cash_cost(item, amount)", b"get_cash_cost(item, 1)", "buy_item charges one piece only",
     ["test_buying_an_item_with_cash_puts_it_in_the_inventory"]),
    (S, 2719, b"item_inventory.get(code, 0) + amount", b"amount", "buy_item replaces the inventory count",
     ["test_buying_more_of_an_item_adds_to_what_the_inventory_has"]),
    (S, 2712, b"amount * int(item.get(\"resourceYield\", \"1\"))", b"amount", "bought resource ignores its yield",
     ["test_buying_resources_with_cash_adds_their_yield", "test_buying_rare_resources_with_coins"]),
    (S, 2724, b"do_costs({k: str(int(v.split('|')[0]) * amount) for k, v in costs.items()})", b"do_costs({})",
     "coins cost of a resource not paid", ["test_buying_rare_resources_with_coins"]),
    (S, 2701, b"item = lookup_item_by_code(code)",
     b"item = next((e for e in game_settings['settings']['items']['item'] if e['-code'] == code), "
     b"{'-type': '', 'cost': {}})", "an unknown item code is accepted as an empty item",
     ["test_buying_an_unknown_item_changes_nothing"]),
    (S, 2782, b"unlock_expansion(param['index'])", b"unlock_expansion(param['index'] + 1)",
     "the expansion next to the bought one is unlocked",
     ["test_buying_an_expansion_sets_its_bit", "test_an_expansion_bought_twice_stays_set"]),
    ("game_settings.py", 220, b"expansions[i] | 1 << e", b"expansions[i] ^ 1 << e", "setBit toggles instead of or",
     ["test_an_expansion_bought_twice_stays_set"]),
    (S, 2252, b"-= order[\"units\"]", b"+= order[\"units\"]", "market order adds the units instead of taking",
     ["test_putting_resources_on_the_market_takes_them"]),
    (S, 2251, b"\"aluminum\", \"copper\"", b"\"copper\", \"aluminum\"", "market index order differs from the XML",
     ["test_putting_resources_on_the_market_takes_them"]),
    (S, 2169, b"[market]", b"[]", "market list answers nothing", ["test_putting_resources_on_the_market_takes_them"]),
    (S, 2237, b"+= market[\"units\"]", b"-= market[\"units\"]", "market refund takes again",
     ["test_taking_resources_off_the_market_gives_them_back"]),
    (S, 2244, b"market[\"units\"] = None", b"pass", "removed market order keeps its units",
     ["test_taking_resources_off_the_market_gives_them_back"]),
    (S, 2742, b"item_inventory[param] -= 1", b"item_inventory[param] -= 2", "useItem takes two",
     ["test_using_an_item_takes_one_from_the_inventory"]),
    (S, 2742, b"item_inventory[param] -= 1", b"item_inventory[param] = item_inventory.get(param, 1) - 1",
     "useItem of an item not owned is accepted", ["test_using_an_item_that_is_not_in_the_inventory_changes_nothing"]),
    (S, 2534, b"session['user_object'][\"userInfo\"][\"worldName\"] = name", b"pass", "world name not saved",
     ["test_the_new_world_name_is_saved"]),
    (S, 2502, b"datetime.now().timestamp()", b"datetime.now().timestamp() * 1000", "pillTS in milliseconds",
     ["test_pillaging_marks_the_time_in_the_invaded_save"]),
    (S, 2502, b"[\"invaders\"][\"u\" + str(get_zid())]", b"[\"invaders\"].setdefault(\"u\" + str(get_zid()), {})",
     "pillage of a save not invaded adds an invader", ["test_pillaging_a_save_the_visitor_did_not_invade_changes_nothing"]),
    (S, 2588, b"if int(params[0]) == session", b"if False and int(params[0]) == session",
     "own world loaded as another player's", ["test_loading_the_own_world_gives_the_save"]),
    (S, 2600, b"ally[\"world\"][\"objects\"] = allies[str(params[0])][\"objects\"]", b"pass",
     "ally island objects not shown", ["test_visiting_an_ally_shows_its_island"]),
    (S, 2615, b"ally[\"worldName\"] = save['user_object'][\"userInfo\"][\"worldName\"]", b"pass",
     "other local save's world name not shown", ["test_visiting_another_local_save_shows_its_world"]),
    (S, 2645, b"+= \",\" + str(params[1])", b"= str(params[1])", "a second help replaces the first",
     ["test_more_help_of_the_same_visitor_is_added"]),
    (S, 2648, b"store_session(save)", b"pass", "help request not written to the neighbor's save",
     ["test_helping_a_neighbor_asks_it_to_accept_and_rewards_the_visitor"]),
    ("state_machine.py", 83, b"tend_type += game_item['-subtype']", b"pass", "visitor reward without the subtype",
     ["test_helping_a_neighbor_asks_it_to_accept_and_rewards_the_visitor"]),
    (S, 2659, b"playback_tend=True", b"playback_tend=False", "accepted help is not played back",
     ["test_accepted_help_clears_the_rock"]),
    (S, 2661, b"del session['user_object'][\"visitorHelpRequests\"][params[0]]", b"pass",
     "accepted help stays", ["test_accepted_help_clears_the_rock"]),
    ("state_machine.py", 156, b"energy = max(energy, 0);", b"pass;", "played back help costs energy",
     ["test_accepted_help_clears_the_rock"]),
    (S, 2671, b"del session['user_object'][\"visitorHelpRequests\"][params[0]]",
     b"session['user_object'][\"visitorHelpRequests\"].clear()", "decline drops every visitor's help",
     ["test_declined_help_changes_only_the_requests"]),
]


def run(launcher, tests, timeout):
    env = dict(os.environ, PYTHONPATH=os.getcwd(), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    start = time.time()
    try:
        out = subprocess.run([sys.executable, launcher, "-q", "-p", "no:cacheprovider"] + [T + t for t in tests],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        return "killed", time.time() - start, ""
    tail = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    return ("pass" if out.returncode == 0 else "fail"), time.time() - start, tail


def main(launcher, out_path):
    with open(out_path, "w", encoding="utf-8") as out:
        for path, line, old, new, description, tests in MUTANTS:
            original = open(path, "rb").read()
            lines = original.splitlines(keepends=True)
            assert lines[line - 1].count(old) == 1, (path, line, old, lines[line - 1])
            before, _, _ = run(launcher, tests, 120)
            lines[line - 1] = lines[line - 1].replace(old, new)
            try:
                open(path, "wb").write(b"".join(lines))
                after, seconds, tail = run(launcher, tests, 120)
            finally:
                open(path, "wb").write(original)
            assert open(path, "rb").read() == original
            record = {"tests": tests, "mutant": description, "where": "%s:%d" % (path, line),
                      "change": [old.decode(), new.decode()], "before": before, "after": after,
                      "after_summary": tail}
            print(json.dumps(record, ensure_ascii=False), flush=True)
            out.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
