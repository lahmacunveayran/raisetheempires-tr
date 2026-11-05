"""Second pass for the survivors of mut_harness.py (denetim2): the first pass ran only the tests that are about the
file (to keep the run short), so a survivor may still be killed by another test file. This runs each survivor again
against the WHOLE suite (minus the two slow bot balance tests, which only check bot_empires' own model) and writes
the result as "full_status" into the result JSON. Only writes into the worktree given with --wt.
Usage: python mut_recheck.py --wt <worktree> --json mut_save_engine.json [--json ...]
"""
import argparse
import json
import os
import subprocess
import time

from mutmut import Context, mutate

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(HERE, "run_pytest_denetim2.py")
TESTS = ["test", "--deselect", "test/bot_empires_test.py::test_the_easy_bots_are_beaten_more_often",
         "--deselect", "test/bot_empires_test.py::test_bot_units_have_their_animations"]


def run(wt, timeout):
    env = dict(os.environ, PYTHONPATH=wt, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.Popen([PY, LAUNCHER, "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + TESTS, cwd=wt,
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        p.communicate()
        return "timeout", ""
    text = out.decode("utf-8", "replace")
    failed = [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]
    return ("survived" if p.returncode == 0 else "killed" if p.returncode == 1 else "error"), (failed[0] if failed else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wt", required=True)
    ap.add_argument("--json", action="append", required=True)
    ap.add_argument("--timeout", type=float, default=300)
    a = ap.parse_args()
    status, _ = run(a.wt, 900)
    assert status == "survived", "baseline of the whole suite fails"
    for name in a.json:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        fname = d["meta"]["file"]
        src_path = os.path.join(a.wt, fname)
        with open(src_path, encoding="utf-8", newline="") as f:
            original = f.read()
        ctx = Context(source=original, filename=fname)
        mutate(ctx)
        mids = ctx.performed_mutation_ids
        if d["meta"]["ranges"]:
            ranges = [tuple(map(int, p.split("-"))) for p in d["meta"]["ranges"].split(",")]
            mids = [m for m in mids if any(lo <= m.line_number + 1 <= hi for lo, hi in ranges)]
        try:
            for key, r in sorted(d["results"].items(), key=lambda kv: int(kv[0])):
                if r["status"] != "survived" or "full_status" in r:
                    continue
                m = mids[int(key)]
                assert m.line_number + 1 == r["line"], (key, m.line_number + 1, r["line"])
                mutated, count = mutate(Context(source=original, filename=fname, mutation_id=m))
                assert count == 1
                with open(src_path, "w", encoding="utf-8", newline="") as f:
                    f.write(mutated)
                t = time.time()
                try:
                    st, detail = run(a.wt, a.timeout)
                finally:
                    with open(src_path, "w", encoding="utf-8", newline="") as f:
                        f.write(original)
                r["full_status"], r["full_detail"] = st, detail
                print(name, key, "line", r["line"], st, round(time.time() - t, 1), detail[:120], flush=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=1, ensure_ascii=False)
        finally:
            with open(src_path, "w", encoding="utf-8", newline="") as f:
                f.write(original)


if __name__ == "__main__":
    main()
