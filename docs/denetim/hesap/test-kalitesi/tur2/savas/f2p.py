"""Fail-to-pass evidence (savas): each entry puts a fault back into the worktree copy (one exact text replacement,
which must occur exactly once), runs the guarding test(s), restores the file, then runs them again on the restored
file. One JSON line per entry into f2p.jsonl."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.join(os.environ["USERPROFILE"], "Desktop", "Raise", "raisetheempires-pr", ".claude", "worktrees",
                  "agent-a3fc98741cb7d98c8")
PY = os.path.join(os.environ["USERPROFILE"], "Desktop", "Raise", "venv312", "Scripts", "python.exe")
LAUNCHER = os.path.join(HERE, "run_pytest_savas.py")


def run(tests):
    env = dict(os.environ, PYTHONPATH=WT, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, LAUNCHER, "-q", "-p", "no:cacheprovider", "-p", "no:warnings", "-p", "no:logging"] + tests,
                       cwd=WT, env=env, capture_output=True, timeout=600)
    text = p.stdout.decode("utf-8", "replace")
    summary = [l for l in text.splitlines() if " passed" in l or " failed" in l][-1:]
    return ("pass" if p.returncode == 0 else "fail"), (summary or [text[-200:]])[0]


def main():
    entries = json.load(open(sys.argv[1], encoding="utf-8"))
    out = open(os.path.join(HERE, "f2p.jsonl"), "a", encoding="utf-8")
    for e in entries:
        path = os.path.join(WT, e["file"])
        original = open(path, "rb").read()
        text = original.decode("utf-8")
        old, new = e["old"], e["new"]
        if "\r\n" in text:
            old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
        assert text.count(old) == 1, ("not exactly once", e["mutant"], text.count(old))
        line = text[:text.index(old)].count("\n") + 1
        try:
            open(path, "wb").write(text.replace(old, new).encode("utf-8"))
            before = run(e["tests"])
        finally:
            open(path, "wb").write(original)
        after = run(e["tests"])
        rec = {"test": e["tests"], "mutant": e["mutant"], "where": "%s:%d" % (e["file"], line),
               "with_fault": before, "fixed": after}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
