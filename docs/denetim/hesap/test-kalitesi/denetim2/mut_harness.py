"""Mutation testing harness (denetim2) built on mutmut 2.5.1's own mutation operators.

mutmut's `mutate()` makes each mutant exactly as `mutmut run` would. This harness only adds what mutmut 2 lacks on
this machine: a seeded random sample of the mutants (the full runs would take ~12 h), a restriction to line ranges
(the save/session parts of empires-server.py), and a per-mutant record in JSON (resumable).

It ONLY ever writes into the worktree given with --wt (a `git worktree` copy), never into the real repository.

Usage:
  python mut_harness.py --wt <worktree> --file battle_engine.py --sample 200 --seed 1 --out res_battle.json \
      --tests test/battle_turn_test.py test/battle_test.py ...
  python mut_harness.py ... --list        (only count the mutants, per covered / not covered line)

Result per mutant: killed (tests failed), survived (tests passed), timeout, error (collection/import error:
counted as killed, as mutmut does). Lines not run by the suite (coverage.json of the whole suite) are marked.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time

import mutmut
from mutmut import Context, RelativeMutationID, mutate

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(HERE, "run_pytest_denetim2.py")


def parse_ranges(text):
    out = []
    for part in (text or "").split(","):
        if part.strip():
            a, b = part.split("-")
            out.append((int(a), int(b)))
    return out


def enumerate_mutants(source, filename):
    ctx = Context(source=source, filename=filename)
    mutate(ctx)
    return ctx.performed_mutation_ids


def covered_lines(cov_json, filename, source):
    """The source lines whose statement the whole suite ran (coverage.json, made with coverage run --branch).
    coverage records a statement under its first line; the other lines of a statement that spans several lines
    (and the header lines of an if/for/def) count with it."""
    import ast
    with open(cov_json, encoding="utf-8") as f:
        d = json.load(f)
    executed = set()
    for name, v in d["files"].items():
        if os.path.normcase(name) == os.path.normcase(filename):
            executed = set(v["executed_lines"])
    owner = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.stmt):
            body = getattr(node, "body", None)
            end = body[0].lineno - 1 if isinstance(body, list) and body else node.end_lineno
            start = min([node.lineno] + [dec.lineno for dec in getattr(node, "decorator_list", [])])
            for line in range(start, max(end, node.lineno) + 1):
                owner[line] = node.lineno
    return {line for line, stmt in owner.items() if stmt in executed}


def run_tests(wt, tests, timeout):
    env = dict(os.environ, PYTHONPATH=wt, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    cmd = [PY, LAUNCHER, "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + tests
    t = time.time()
    p = subprocess.Popen(cmd, cwd=wt, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        out, _ = p.communicate()
        return "timeout", time.time() - t, out.decode("utf-8", "replace")[-1500:]
    text = out.decode("utf-8", "replace")
    return p.returncode, time.time() - t, text[-1500:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wt", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--tests", nargs="+", required=True)
    ap.add_argument("--sample", type=int, default=0, help="0 = all")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--ranges", default="", help="1-based inclusive line ranges, e.g. 100-213,896-1003")
    ap.add_argument("--cov", default=os.path.join(HERE, "coverage.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=0, help="0 = 3 x baseline + 30 s")
    ap.add_argument("--deselect", action="append", default=[], help="a test id to leave out (pytest --deselect)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--covered-only", action="store_true",
                    help="sample only mutants on lines the suite runs (the others cannot be killed)")
    a = ap.parse_args()
    for test_id in a.deselect:
        a.tests += ["--deselect", test_id]

    path = os.path.join(a.wt, a.file)
    with open(path, encoding="utf-8", newline="") as f:
        original = f.read()
    mids = enumerate_mutants(original, a.file)
    ranges = parse_ranges(a.ranges)
    if ranges:
        mids = [m for m in mids if any(lo <= m.line_number + 1 <= hi for lo, hi in ranges)]
    cov = covered_lines(a.cov, a.file, original)
    n_cov = sum(1 for m in mids if m.line_number + 1 in cov)
    print("mutants", len(mids), "on covered lines", n_cov, "on lines never run", len(mids) - n_cov, flush=True)
    if a.list:
        return
    rng = random.Random(a.seed)
    pool = [i for i, m in enumerate(mids) if not a.covered_only or (m.line_number + 1) in cov]
    sample = sorted(rng.sample(pool, a.sample)) if a.sample and a.sample < len(pool) else pool

    results = {}
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as f:
            results = json.load(f)["results"]
    meta = {"file": a.file, "total_mutants": len(mids), "on_covered_lines": n_cov, "sample": len(sample),
            "seed": a.seed, "ranges": a.ranges, "tests": a.tests, "covered_only": a.covered_only}

    rc, base_t, text = run_tests(a.wt, a.tests, 900)
    if rc != 0:
        print("BASELINE FAILS", rc, text)
        sys.exit(1)
    timeout = a.timeout or 3 * base_t + 30
    meta["baseline_seconds"] = round(base_t, 1)
    print("baseline ok", round(base_t, 1), "s; timeout", round(timeout), flush=True)

    try:
        for n, i in enumerate(sample):
            key = str(i)
            if key in results:
                continue
            m = mids[i]
            ctx = Context(source=original, filename=a.file, mutation_id=m)
            mutated, count = mutate(ctx)
            assert count == 1
            orig_lines, mut_lines = original.split("\n"), mutated.split("\n")
            new_line = mut_lines[m.line_number] if len(mut_lines) == len(orig_lines) else "(lines changed)"
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(mutated)
            try:
                for attempt in range(3):
                    rc, t, text = run_tests(a.wt, a.tests, timeout)
                    if "SingleInstanceException" in text or "Another instance" in text:
                        time.sleep(5)
                        continue
                    break
            finally:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(original)
            status = ("survived" if rc == 0 else "killed" if rc == 1 else "timeout" if rc == "timeout"
                      else "error")
            results[key] = {"line": m.line_number + 1, "index": m.index, "original": m.line.strip(),
                            "mutant": new_line.strip(), "status": status, "covered": (m.line_number + 1) in cov,
                            "seconds": round(t, 1), "tail": text[-300:] if status in ("survived", "error") else ""}
            print(n + 1, "/", len(sample), "line", m.line_number + 1, status, round(t, 1), flush=True)
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump({"meta": meta, "results": results}, f, indent=1, ensure_ascii=False)
    finally:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(original)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results}, f, indent=1, ensure_ascii=False)
    st = [r["status"] for r in results.values()]
    print({s: st.count(s) for s in set(st)})


if __name__ == "__main__":
    main()
