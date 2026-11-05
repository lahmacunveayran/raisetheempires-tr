"""f2p.py <spec.py>: spec defines LABEL, MUTATIONS=[(file, old, new)], TESTS=[nodeids], or CASES=[(label, mutations, tests)].
Applies the mutations (reverting the fix), runs the tests, restores the files, appends results to f2p.jsonl.
Run from the worktree root."""
import json, os, runpy, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))
spec = runpy.run_path(sys.argv[1])
cases = spec.get("CASES") or [(spec["LABEL"], spec["MUTATIONS"], spec["TESTS"])]
for label, mutations, tests in cases:
    originals = {}
    try:
        for f, old, new in mutations:
            cur = open(f, "rb").read()
            originals.setdefault(f, cur)
            o, n = old.encode(), new.encode()
            if b"\r\n" in cur:
                o, n = o.replace(b"\n", b"\r\n"), n.replace(b"\n", b"\r\n")
            assert cur.count(o) == 1, (f, cur.count(o), old[:80])
            open(f, "wb").write(cur.replace(o, n))
        results = {}
        for t in tests:
            r = subprocess.run([sys.executable, os.path.join(here, "run_pytest_inceleme.py"), "-q", "-p", "no:cacheprovider", t],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            results[t] = "pass" if r.returncode == 0 else "FAIL"
    finally:
        for f, data in originals.items():
            open(f, "wb").write(data)
    line = {"label": label, "with_fix_reverted": results}
    with open(os.path.join(here, "f2p.jsonl"), "a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")
    print(json.dumps(line))
