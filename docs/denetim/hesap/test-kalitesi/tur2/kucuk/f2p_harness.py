"""Fail-to-pass check: apply each mutant to the worktree, run the new tests and the old ones (cb00c06), restore.

Run from the worktree root: python f2p_harness.py [mutant ids]. Writes f2p.jsonl next to this script.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LAUNCHER = os.path.join(HERE, "run_pytest_kucuk.py")
OLD = os.path.join(HERE, "old")
ROOT = os.getcwd()
TIMEOUT = 300

M = [
    # id, file, old, new, description, new tests, old tests (file::test or file)
    ("S2", "slot_machine.py", "random.choices(loot, weights=[weight for _, _, weight in loot])[0]",
     "random.choices(loot)[0]", "slot spin ignores the weights (uniform draw)",
     "test/slot_machine_test.py", "slot_machine_test.py"),
    ("S3", "slot_machine.py", '{"_type": code, "_count": str(amount)}', '{"_type": code, "_count": str(amount * 2)}',
     "slot gives twice the amount of a resource prize", "test/slot_machine_test.py", "slot_machine_test.py"),
    ("S7", "slot_machine.py", '"buildablepart": 12', '"buildablepart": 6',
     "slot weight of building parts 12 -> 6", "test/slot_machine_test.py", "slot_machine_test.py"),
    ("V1", "treasure_vault.py", "random.choices(loot, weights=[weight for _, _, weight in loot])[0]",
     "random.choices(loot)[0]", "vault draw ignores the weights (uniform)",
     "test/treasure_vault_test.py", "treasure_vault_test.py"),
    ("V2", "treasure_vault.py", "random.choices(loot, weights=[weight for _, _, weight in loot])[0]",
     'random.choices(loot, weights=[0 if code == "N36" else weight for code, _, weight in loot])[0]',
     "vault never gives N36 (one item can never come out)", "test/treasure_vault_test.py",
     "treasure_vault_test.py"),
    ("V3", "treasure_vault.py", '{"_type": code, "_count": str(amount)}', '{"_type": code, "_count": str(amount // 2)}',
     "vault gives half the amount of a resource prize", "test/treasure_vault_test.py", "treasure_vault_test.py"),
    ("V6", "treasure_vault.py", '"handler": "addLootToInventory", "loot": name,',
     '"handler": "addLootToInventory", "loot": code,',
     "vault response names an item prize by code in loot (client icon by name breaks)",
     "test/treasure_vault_test.py", "treasure_vault_test.py"),
    ("M1", "megaseries.py", "            if node.get('-quest')]", "            if node.get('-quest')][:-1]",
     "megaseries.nodes drops the reward quest", "test/megaseries_test.py", "megaseries_test.py"),
    ("M2", "megaseries.py", "for stage in _as_list(series.get('stage'))",
     "for stage in reversed(_as_list(series.get('stage')))", "megaseries.nodes plays the stages backwards",
     "test/megaseries_test.py", "megaseries_test.py"),
    ("M4", "megaseries.py", "PLAYABLE = [series_id for series_id, series in SERIES.items() if playable(series)]",
     "PLAYABLE = [series_id for series_id, series in SERIES.items() if playable(series)][::-1]",
     "mega series offered in reverse XML order", "test/megaseries_test.py", "megaseries_test.py"),
    ("Q1", "quest_trees.py", "return roots[0] if roots else None", "return roots[-1] if roots else None",
     "first_quest returns the last root", "test/quest_trees_test.py", "quest_trees_test.py"),
    ("Q2", "quest_trees.py", "trees[tree['-id']] = tree  # some ids", "trees.setdefault(tree['-id'], tree)  # some ids",
     "duplicate tree id keeps the first questTree", "test/quest_trees_test.py", "quest_trees_test.py"),
    ("Q3", "quest_trees.py", "if surrounding >= 6 and", "if surrounding >= 5 and",
     "hook_spots land threshold 6 -> 5", "test/quest_trees_test.py", "quest_trees_test.py"),
    ("Q4", "quest_trees.py", "spot = _cells(x - 1, y - 1, HOOK_SIZE + 2, HOOK_SIZE + 2)  # keep spots apart",
     "spot = _cells(x, y, HOOK_SIZE, HOOK_SIZE)  # keep spots apart", "hook spots no longer kept apart",
     "test/quest_trees_test.py", "quest_trees_test.py"),
    ("Q5", "quest_trees.py", "count = int(tree.get('-totalQuestTreeAllies', 2))",
     "count = int(tree.get('-totalQuestTreeAllies', 3))", "allies default 2 -> 3",
     "test/quest_trees_test.py", "quest_trees_test.py"),
    ("Q6", "quest_trees.py", "    if quest not in started:\n        started.append(quest)",
     "    started.append(quest)", "starting a node twice lists it twice",
     "test/quest_trees_test.py", "quest_trees_test.py"),
    ("Q7", "quest_trees.py", "PLAYABLE = [tree_id for tree_id, tree in TREES.items() if playable(tree)]",
     "PLAYABLE = [tree_id for tree_id, tree in TREES.items() if playable(tree)][::-1]",
     "trees offered in reverse XML order", "test/quest_trees_test.py", "quest_trees_test.py"),
    ("B1", "bot_empires.py", 'and i.get("-buyable") == "true" and "requiredDate" not in i and',
     'and i.get("-buyable") == "true" and', "regular army includes event units (STRENGTH_PER_LEVEL fit changes)",
     "test/bot_empires_test.py::test_units_get_stronger_by_a_few_percent_a_level",
     "bot_empires_test.py::test_units_get_stronger_by_a_few_percent_a_level"),
    ("B2", "bot_empires.py", "    return math.exp(slope)", "    return math.exp(slope * 1.1)",
     "STRENGTH_PER_LEVEL 10% steeper than the fit",
     "test/bot_empires_test.py::test_units_get_stronger_by_a_few_percent_a_level",
     "bot_empires_test.py::test_units_get_stronger_by_a_few_percent_a_level"),
    ("B3", "bot_empires.py", "HANDICAP = 2.5", "HANDICAP = 0", "bots not handicapped (exact mirror)",
     "test/bot_empires_test.py::test_the_easy_bots_are_beaten_more_often",
     "bot_empires_test.py::test_the_easy_bots_are_beaten_more_often"),
    ("B4", "bot_empires.py", "HANDICAP = 2.5", "HANDICAP = 6", "bots too weak (handicap 6 levels)",
     "test/bot_empires_test.py::test_the_easy_bots_are_beaten_more_often",
     "bot_empires_test.py::test_the_easy_bots_are_beaten_more_often"),
]


def run(targets):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    start = time.time()
    try:
        p = subprocess.run([PY, LAUNCHER, "-q", "-p", "no:cacheprovider", "-rf"] + targets, cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "killed", [], time.time() - start
    failed = sorted(set(re.findall(r"^FAILED (\S+?)(?: - |$)", p.stdout, re.M)))
    summary = (re.findall(r"=+ (.*(?:passed|failed|error).*) in ", p.stdout) or ["rc %d" % p.returncode])[-1]
    return summary, failed, time.time() - start


def line_of(path, text):
    data = open(path, encoding="utf-8").read()
    return data[:data.index(text)].count("\n") + 1


def main(ids):
    out = open(os.path.join(HERE, "f2p.jsonl"), "a", encoding="utf-8")
    for mid, path, old, new, desc, new_tests, old_tests in M:
        if ids and mid not in ids:
            continue
        original = open(path, "rb").read()
        text = original.decode("utf-8")
        lineno = line_of(path, old)  # text mode reads CRLF as \n
        if "\r\n" in text:
            old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
        assert text.count(old) == 1, (mid, text.count(old))
        old_file, _, old_test = old_tests.partition("::")
        copied = os.path.join("test", "f2pold_" + old_file)
        shutil.copy(os.path.join(OLD, old_file), copied)
        try:
            open(path, "wb").write(text.replace(old, new).encode("utf-8"))
            new_sum, new_failed, t1 = run([new_tests])
            old_sum, old_failed, t2 = run([copied + ("::" + old_test if old_test else "")])
        finally:
            open(path, "wb").write(original)
            os.remove(copied)
        rec = {"mutant": mid, "description": desc, "file_line": "%s:%d" % (path, lineno), "new_tests": new_tests,
               "clean": "all pass (full suite run)", "mutant_new_result": new_sum, "new_failed": new_failed,
               "mutant_old_result(cb00c06 tests)": old_sum, "old_failed": old_failed,
               "seconds": round(t1 + t2, 1)}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
