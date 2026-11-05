"""f2p_head.py <label> <file> <test>...: runs the tests with <file> taken from git HEAD (the commit before the fix), restores it."""
import json, os, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))
label, f, tests = sys.argv[1], sys.argv[2], sys.argv[3:]
original = open(f, "rb").read()
try:
    open(f, "wb").write(subprocess.run(["git", "show", "HEAD:" + f], capture_output=True, check=True).stdout)
    results = {}
    for t in tests:
        r = subprocess.run([sys.executable, os.path.join(here, "run_pytest_inceleme.py"), "-q", "-p", "no:cacheprovider", t],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        results[t] = "pass" if r.returncode == 0 else "FAIL"
        tail = [l for l in r.stdout.splitlines() if "Error" in l][:2]
        if tail:
            results[t + " (why)"] = tail
finally:
    open(f, "wb").write(original)
line = {"label": label, "with_fix_reverted": results}
with open(os.path.join(here, "f2p.jsonl"), "a", encoding="utf-8") as out:
    out.write(json.dumps(line) + "\n")
print(json.dumps(line, indent=1))
