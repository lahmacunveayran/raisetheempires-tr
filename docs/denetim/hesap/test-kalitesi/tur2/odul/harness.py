"""Applies each mutant of mutants.py to <wt>/battle_engine.py (bytes, line endings kept), runs the tests with a
timeout (the process tree is killed after it, counted killed), restores the file. Writes one JSON line per mutant.

usage: python harness.py <wt> <out.jsonl> [--ids a,b,c] [--timeout s] -- <pytest args>
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mutants import MUTANTS  # noqa: E402

PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(HERE, "run_pytest_odul.py")


def run(wt, tests, timeout):
    env = dict(os.environ, PYTHONPATH=wt, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    cmd = [PY, LAUNCHER, "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + tests
    t = time.time()
    p = subprocess.Popen(cmd, cwd=wt, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        out, _ = p.communicate()
        return "timeout", time.time() - t, out.decode("utf-8", "replace")
    return p.returncode, time.time() - t, out.decode("utf-8", "replace")


def first_failure(text):
    return [line.split(" - ")[0] for line in text.splitlines() if line.startswith("FAILED") or line.startswith("ERROR")]


def main():
    args = sys.argv[1:]
    sep = args.index("--")
    opts, tests = args[:sep], args[sep + 1:]
    wt, out = opts[0], opts[1]
    ids = None
    timeout = 400
    if "--ids" in opts:
        ids = set(opts[opts.index("--ids") + 1].split(","))
    if "--timeout" in opts:
        timeout = float(opts[opts.index("--timeout") + 1])
    path = os.path.join(wt, "battle_engine.py")
    with open(path, "rb") as f:
        original = f.read()
    lines = original.split(b"\n")
    rc, base, text = run(wt, tests, 900)
    if rc != 0:
        print("BASELINE FAILS", rc, text[-2000:])
        sys.exit(1)
    print("baseline", round(base, 1), "s", flush=True)
    try:
        for mid, line, old, new, kind in MUTANTS:
            if ids and mid not in ids:
                continue
            src = lines[line - 1].decode("utf-8")
            assert src.count(old) == 1, (mid, line, src)
            mutated = lines[:]
            mutated[line - 1] = src.replace(old, new).encode("utf-8")
            with open(path, "wb") as f:
                f.write(b"\n".join(mutated))
            try:
                rc, t, text = run(wt, tests, timeout)
            finally:
                with open(path, "wb") as f:
                    f.write(original)
            status = "survived" if rc == 0 else "timeout" if rc == "timeout" else "killed" if rc == 1 else "error"
            rec = {"id": mid, "line": line, "old": old, "new": new, "kind": kind, "status": status,
                   "seconds": round(t, 1), "first_failure": first_failure(text)}
            print(json.dumps(rec, ensure_ascii=False), flush=True)
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        with open(path, "wb") as f:
            f.write(original)
        with open(path, "rb") as f:
            assert f.read() == original


if __name__ == "__main__":
    main()
