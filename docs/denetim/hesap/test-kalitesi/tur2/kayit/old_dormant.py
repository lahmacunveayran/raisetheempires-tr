"""B-D5 f2p: the old dormant-tree test (cb00c06) passes with the 'dormant click still gives rewards' mutant,
the new one fails. Writes the old test to test/_old_dormant_test.py, runs both against the mutant, removes the file."""
import json
import os
import subprocess

WT = r"C:\Users\<user>\Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-a60a9e23f98052837"
K = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(K, "run_pytest_kayit_mut.py")
OLD = '                      "has no click transition. Ignoring click.")\r\n                return'
NEW = ('                      "has no click transition. Ignoring click.")\r\n'
       '                do_state_rewards(state, cur_object.get(\'referenceItem\'), meta, playback_tend=playback_tend)\r\n'
       '                return')

src = subprocess.run(["git", "show", "cb00c06:test/empires_test.py"], cwd=WT, capture_output=True).stdout.decode()
src = src.replace("\r\n", "\n")
start = src.index("def test_click_on_dormant_tree_is_ignored")
end = src.index("def test_place_item_without_cost")
header = src[:src.index("TEST_DIR = Path(__file__).parent")] + "TEST_DIR = Path(__file__).parent\n\n\n"
tmp = os.path.join(WT, "test", "_old_dormant_test.py")
sm = os.path.join(WT, "state_machine.py")
original = open(sm, encoding="utf-8", newline="").read()
assert original.count(OLD) == 1
env = dict(os.environ, PYTHONPATH=WT, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
results = {}
try:
    open(tmp, "w", encoding="utf-8").write(header + src[start:end])
    for label, text in (("clean", original), ("mutant", original.replace(OLD, NEW))):
        open(sm, "w", encoding="utf-8", newline="").write(text)
        for name, node in (("old", "test/_old_dormant_test.py::test_click_on_dormant_tree_is_ignored"),
                           ("new", "test/empires_test.py::test_click_on_dormant_tree_is_ignored")):
            p = subprocess.run([PY, LAUNCHER, "-q", "-p", "no:cacheprovider", "-p", "no:warnings", node], cwd=WT,
                               env=env, capture_output=True, timeout=200)
            results[(label, name)] = "passed" if p.returncode == 0 else "failed"
finally:
    open(sm, "w", encoding="utf-8", newline="").write(original)
    os.remove(tmp)
print(results)
line = original[:original.index(OLD)].count("\n") + 1
with open(os.path.join(K, "f2p.jsonl"), "a", encoding="utf-8") as out:
    for name in ("old", "new"):
        out.write(json.dumps({"test": ("cb00c06 " if name == "old" else "") +
                              "test/empires_test.py::test_click_on_dormant_tree_is_ignored",
                              "mutant": "dormant click still gives the state's rewards",
                              "where": "state_machine.py:%d" % line, "before": results[("clean", name)],
                              "after": results[("mutant", name)]}) + "\n")
