"""Re-applies the surviving mutants of two lists to the worktree copy and runs the battle tests on each (savas, fix2).

Lists:
  A: mutmut_A_survivors.txt (diff blocks of cb00c06, battle_engine.py and titan_lab.py)
  G: denetim2/mut_battle_engine.json, the battle_engine survivors the audit classified G (and E, for the record)
A mutant is one line: the cb00c06 line text -> the mutant text. Its line in today's file is found by mapping the
cb00c06 line number with difflib and taking the line of the same text nearest to it; when the text is no longer
in the file the mutant is reported as 'rewritten'. The file is always restored (also on errors / Ctrl-C).
Usage: python mut_savas.py out.json [--only A|G] [--ids 3,5]
"""
import difflib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(os.path.dirname(HERE))
WT = os.path.join(os.environ["USERPROFILE"], "Desktop", "Raise", "raisetheempires-pr", ".claude", "worktrees",
                  "agent-a3fc98741cb7d98c8")
PY = os.path.join(os.environ["USERPROFILE"], "Desktop", "Raise", "venv312", "Scripts", "python.exe")
LAUNCHER = os.path.join(HERE, "run_pytest_savas.py")
TESTS = ["test/battle_turn_test.py", "test/battle_test.py", "test/titan_lab_test.py", "test/bot_empires_test.py",
         "test/empires_test.py", "test/bounty_center_test.py",
         "--deselect", "test/bot_empires_test.py::test_the_easy_bots_are_beaten_more_often",
         "--deselect", "test/bot_empires_test.py::test_bot_units_have_their_animations"]
OLD = {"battle_engine.py": os.path.join(HERE, "battle_engine.cb00c06.py"),
       "titan_lab.py": os.path.join(HERE, "titan_lab.cb00c06.py")}


def list_a():
    text = open(os.path.join(S, "mutmut_A_survivors.txt"), encoding="utf-8").read()
    out = []
    for block in text.split("=== ")[1:]:
        lines = block.splitlines()
        mid = lines[0].strip()
        start = int(re.match(r"@@ -(\d+)", lines[1]).group(1))
        minus = next(l[1:] for l in lines[2:] if l.startswith("-"))
        plus = next(l[1:] for l in lines[2:] if l.startswith("+"))
        out.append({"list": "A", "id": mid, "file": "titan_lab.py" if int(mid) >= 290 else "battle_engine.py",
                    "line": start + 3, "original": minus.strip(), "mutant": plus.strip()})
    return out


def list_g():
    spec = importlib.util.spec_from_file_location("mut_survivors", os.path.join(S, "denetim2", "mut_survivors.py"))
    ms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ms)
    classes = ms.CLASS["mut_battle_engine.json"]
    res = json.load(open(os.path.join(S, "denetim2", "mut_battle_engine.json"), encoding="utf-8"))["results"]
    return [{"list": "G", "id": k, "file": "battle_engine.py", "line": res[k]["line"], "original": res[k]["original"],
             "mutant": res[k]["mutant"], "audit": c[0], "why": c[1]} for k, c in classes.items()]


def line_map(old_lines, new_lines):
    m = {}
    sm = difflib.SequenceMatcher(None, [l.strip() for l in old_lines], [l.strip() for l in new_lines], autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for i in range(n):
            m[a + i + 1] = b + i + 1
    return m


def run_tests(timeout):
    env = dict(os.environ, PYTHONPATH=WT, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    cmd = [PY, LAUNCHER, "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings", "-p", "no:logging"] + TESTS
    t = time.time()
    p = subprocess.Popen(cmd, cwd=WT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        p.communicate()
        return "timeout", time.time() - t, ""
    text = out.decode("utf-8", "replace")
    first = next((l for l in text.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")), "")
    return ("survived" if p.returncode == 0 else "killed" if p.returncode == 1 else "error"), time.time() - t, \
        first or text[-300:]


def main():
    out_path = sys.argv[1]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    ids = set(sys.argv[sys.argv.index("--ids") + 1].split(",")) if "--ids" in sys.argv else None
    mutants = [m for m in list_a() + list_g() if (only is None or m["list"] == only) and (ids is None or m["id"] in ids)]
    results = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    status, base, text = run_tests(900)
    assert status == "survived", ("baseline fails", text)
    timeout = 10 * base + 30
    print("baseline", round(base), "s, timeout", round(timeout), flush=True)
    for m in mutants:
        key = m["list"] + m["id"]
        if key in results:
            continue
        path = os.path.join(WT, m["file"])
        original = open(path, "rb").read()
        sep = "\r\n" if b"\r\n" in original else "\n"
        new_lines = original.decode("utf-8").split(sep)
        old_lines = open(OLD[m["file"]], "rb").read().decode("utf-8").replace("\r\n", "\n").split("\n")
        mapped = line_map(old_lines, new_lines).get(m["line"])
        candidates = [i + 1 for i, l in enumerate(new_lines) if l.strip() == m["original"]]
        r = dict(m)
        if not candidates:
            r.update(status="rewritten", at=None)
        else:
            at = mapped if mapped in candidates else min(candidates, key=lambda c: abs(c - (mapped or m["line"])))
            line = new_lines[at - 1]
            new_lines[at - 1] = line[:len(line) - len(line.lstrip())] + m["mutant"]
            try:
                open(path, "wb").write(sep.join(new_lines).encode("utf-8"))
                st, t, detail = run_tests(timeout)
            finally:
                open(path, "wb").write(original)
            r.update(status=st, at=at, seconds=round(t, 1), detail=detail[-300:])
        results[key] = r
        print(key, r["status"], r.get("at"), r.get("seconds"), (r.get("detail") or "")[:120], flush=True)
        json.dump(results, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
