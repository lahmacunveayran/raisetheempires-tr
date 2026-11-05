"""Hand-made ("targeted") mutants of the behaviours the tests say they protect (denetim2).

Each mutant is one text replacement in one production file of the worktree (--wt), checked to occur exactly once;
the tests that are about that behaviour are run, and the file is put back. Writes targeted_mutants.json.
Usage: python targeted_mutants.py --wt <worktree>
"""
import argparse
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(HERE, "run_pytest_denetim2.py")

BATTLE = ["test/battle_turn_test.py", "test/battle_test.py", "test/titan_lab_test.py", "test/bot_empires_test.py",
          "test/empires_test.py", "test/bounty_center_test.py",
          "--deselect", "test/bot_empires_test.py::test_the_easy_bots_are_beaten_more_often",
          "--deselect", "test/bot_empires_test.py::test_bot_units_have_their_animations"]
SAVE = ["test/session_layer_test.py", "test/empires_test.py", "test/save_actions_test.py",
        "test/state_machine_test.py"]

MUTANTS = [
    # id, file, old, new, tests, what the change breaks
    ("B1", "battle_engine.py", "    return math.floor(x + 0.5)", "    return round(x)", BATTLE,
     "Math.round of the client replaced by Python's round (halves to even)"),
    ("B2", "battle_engine.py", "            damage *= float(a['-mod'])\n            break",
     "            damage *= float(a['-mod'])", BATTLE, "every matching <against> of a power multiplies (no first-match)"),
    ("B3", "battle_engine.py", "            if baddie_strengths[enemy_unit_id] == 1:", "            if False:", BATTLE,
     "an enemy unit can be left at 1 strength"),
    ("B4", "battle_engine.py", "        elif roll != 2 and roll >= crit:", "        elif roll >= crit:", BATTLE,
     "a STRONG_ROLL (weak defender) also counts as a critical hit"),
    ("B5", "battle_engine.py", "        damage = math.floor(damage * 10 ** 3) / 10 ** 3", "        damage = damage", BATTLE,
     "damage no longer cut to 3 digits before ceil"),
    ("B6", "battle_engine.py", "        glance = 0.10", "        glance = 0.15", BATTLE,
     "glancing multiplier 0.15 instead of combatGlancingBlowMultiplier 0.10"),
    ("B7", "battle_engine.py", "    opposite_day =  third_random < 0.2", "    opposite_day =  third_random < 0.25", BATTLE,
     "combatAISwitchPercent 0.25 instead of 0.2"),
    ("B8", "battle_engine.py", "    if (ratio < 0.5) ^ opposite_day:", "    if (ratio <= 0.5) ^ opposite_day:", BATTLE,
     "switch ratio boundary: <= instead of < (combatAISwitchRatio, exactly 0.5)"),
    ("B9", "battle_engine.py", "        critter = 1.5", "        critter = 1.4", BATTLE,
     "critical multiplier 1.4 instead of combatCriticalHitMultiplier 1.5"),
    ("B10", "battle_engine.py", "            strength = as3_round(strength)", "            strength = math.ceil(strength)",
     BATTLE, "research strength rounded up instead of Math.round"),
    ("S1", "empires-server.py", "            lock.acquire()\n", "            pass\n", SAVE,
     "no lock: two requests of one save run at the same time"),
    ("S2", "empires-server.py",
     "        app.logger.exception(\"Call %s failed, its changes are undone\", reqq.functionName)\n"
     "        if snapshot is not None:\n            session.clear()\n            session.update(pickle.loads(snapshot))",
     "        app.logger.exception(\"Call %s failed, its changes are undone\", reqq.functionName)", SAVE,
     "a failed call's changes are kept"),
    ("S3", "save_engine.py", "    try:\n        yield\n        for save in g.pending_saves:\n            write_session(save)\n"
     "    finally:\n        g.pop(\"pending_saves\", None)",
     "    try:\n        yield\n    finally:\n        for save in g.pending_saves:\n            write_session(save)\n"
     "        g.pop(\"pending_saves\", None)", SAVE, "other saves are written also when the call fails"),
    ("S4", "empires-server.py", "        return host.lower() == \"localhost\"", "        return \"localhost\" in host.lower()",
     SAVE, "any host name with localhost in it is accepted (DNS rebinding)"),
    ("S5", "empires-server.py", "        source = request.headers.get(\"Origin\") or request.headers.get(\"Referer\")",
     "        source = request.headers.get(\"Referer\")", SAVE, "the Origin header is no longer checked"),
    ("S6", "empires-server.py",
     "    if not isinstance(save_game.get('quests'), list) or not validate_save(save_game):",
     "    if not isinstance(save_game.get('quests'), list):", SAVE, "the save editor writes an invalid user_object"),
    ("S7", "empires-server.py", "            if encode is not None:\n                encode(dict(session))",
     "            if False:\n                encode(dict(session))", SAVE,
     "a value the save can't hold is not caught by the call"),
    ("S8", "save_engine.py", "                    (save_id, save_id, MAX_BACKUPS))", "                    (save_id, save_id, MAX_BACKUPS + 1))",
     SAVE, "one backup more than MAX_BACKUPS is kept"),
    ("S9", "empires-server.py", "indent=2).replace(\"<\", \"\\\\u003c\")", "indent=2)", SAVE,
     "a world name can end the page's script"),
    ("S10", "save_engine.py", "        if not data.startswith(b\"\\x80\"):", "        if data.startswith(b\"\\x80\"):", SAVE,
     "pickled saves are not converted (and msgpack ones are tried as pickles)"),
    ("S11", "empires-server.py", "    lock = g.pop(\"save_lock\", None)\n    if lock is not None:\n        lock.release()",
     "    lock = g.pop(\"save_lock\", None)", SAVE, "the save lock is never released"),
    ("S12", "empires-server.py", "    if self.is_asset(request.path):\n            return SecureCookieSession()",
     "    if False:\n            return SecureCookieSession()", SAVE, "asset requests load and write the whole save"),
    ("S13", "save_engine.py", "    for backup in reversed(chain[:MAX_BACKUPS]):", "    for backup in chain[:MAX_BACKUPS]:", SAVE,
     "nested backups moved newest first (ids in the wrong order)"),
    ("S14", "empires-server.py", "    session['save_version'] = save_game.get('save_version')\n",
     "", SAVE, "the save editor keeps the old save_version"),
    # S1 is killed because lock.release() of a lock never taken raises; S1b takes the lock away cleanly (no acquire,
    # no release), so only a test of two overlapping requests can see it
    ("S1b", "empires-server.py", [("            lock.acquire()\n", "            pass\n"),
                                  ("    if lock is not None:\n        lock.release()", "    if lock is not None:\n        pass")],
     None, SAVE, "no lock at all: two requests of one save run at the same time"),
]


def run(wt, tests, timeout=240):
    env = dict(os.environ, PYTHONPATH=wt, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    t = time.time()
    p = subprocess.Popen([PY, LAUNCHER, "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + tests, cwd=wt,
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        p.communicate()
        return "timeout", time.time() - t, ""
    text = out.decode("utf-8", "replace")
    failed = [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR "))]
    return ("survived" if p.returncode == 0 else "killed" if p.returncode == 1 else "error"), time.time() - t, \
        (failed[0] if failed else text.strip().splitlines()[-1] if text.strip() else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wt", required=True)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    out_path = os.path.join(HERE, "targeted_mutants.json")
    results = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    for mid, fname, old, new, tests, what in MUTANTS:
        if a.only and mid not in a.only:
            continue
        path = os.path.join(a.wt, fname)
        with open(path, encoding="utf-8", newline="") as f:
            original = f.read()
        text = original.replace("\r\n", "\n")
        crlf = "\r\n" in original
        pairs = old if isinstance(old, list) else [(old, new)]
        mutated = text
        for o, n in pairs:
            assert mutated.count(o) == 1, (mid, mutated.count(o))
            mutated = mutated.replace(o, n)
        if crlf:
            mutated = mutated.replace("\n", "\r\n")
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(mutated)
            status, secs, detail = run(a.wt, tests)
        finally:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(original)
        results[mid] = {"file": fname, "what": what, "status": status, "seconds": round(secs, 1), "detail": detail}
        print(mid, status, round(secs, 1), detail[:150], flush=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
