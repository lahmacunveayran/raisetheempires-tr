"""Re-apply the audit's (denetim2) surviving mutants to this worktree and run the tests against each, with a timeout.

The mutants are made again with mutmut 2.5.1's own operators from the same source (the files under test are unchanged
since cb00c06), taken by their index in the audit's result JSON; the original line is checked before each run.
Only ever writes into the worktree given; the original file is always written back.

Usage: python remut.py --wt <worktree> --json <audit json> --out <result json> [--timeout s] -- <tests...>
"""
import argparse
import json
import os
import subprocess
import time

from mutmut import Context, mutate

PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_pytest_kayit_mut.py")


def run(wt, tests, timeout):
    env = dict(os.environ, PYTHONPATH=wt, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    cmd = [PY, LAUNCHER, "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + tests
    t = time.time()
    p = subprocess.Popen(cmd, cwd=wt, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        p.communicate()
        return "timeout", "", time.time() - t
    text = out.decode("utf-8", "replace")
    failed = [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]
    status = "survived" if p.returncode == 0 else "killed" if p.returncode == 1 else "error"
    return status, (failed[0] if failed else text[-300:]), time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wt", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--all", action="store_true", help="also the mutants the audit's tests already killed")
    ap.add_argument("tests", nargs="+")
    a = ap.parse_args()
    with open(a.json, encoding="utf-8") as f:
        audit = json.load(f)
    fname = audit["meta"]["file"]
    src_path = os.path.join(a.wt, fname)
    with open(src_path, encoding="utf-8", newline="") as f:
        original = f.read()
    ctx = Context(source=original, filename=fname)
    mutate(ctx)
    mids = ctx.performed_mutation_ids
    if audit["meta"]["ranges"]:
        ranges = [tuple(map(int, p.split("-"))) for p in audit["meta"]["ranges"].split(",")]
        mids = [m for m in mids if any(lo <= m.line_number + 1 <= hi for lo, hi in ranges)]
    results = {}
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as f:
            results = json.load(f)
    status, detail, base = run(a.wt, a.tests, 900)
    assert status == "survived", ("baseline fails", detail)
    print("baseline", round(base, 1), "s", flush=True)
    try:
        for key, r in sorted(audit["results"].items(), key=lambda kv: int(kv[0])):
            before = r.get("full_status", r["status"])
            if key in results or (before != "survived" and not a.all):
                continue
            m = mids[int(key)]
            assert m.line_number + 1 == r["line"] and m.line.strip() == r["original"], (key, m.line, r["original"])
            mutated, count = mutate(Context(source=original, filename=fname, mutation_id=m))
            assert count == 1
            with open(src_path, "w", encoding="utf-8", newline="") as f:
                f.write(mutated)
            try:
                st, detail, t = run(a.wt, a.tests, a.timeout)
            finally:
                with open(src_path, "w", encoding="utf-8", newline="") as f:
                    f.write(original)
            results[key] = {"line": r["line"], "original": r["original"], "mutant": r["mutant"], "audit": before,
                            "now": st, "detail": detail, "seconds": round(t, 1)}
            print(fname, key, "line", r["line"], before, "->", st, round(t, 1), detail[:110], flush=True)
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=1, ensure_ascii=False)
    finally:
        with open(src_path, "w", encoding="utf-8", newline="") as f:
            f.write(original)


if __name__ == "__main__":
    main()
