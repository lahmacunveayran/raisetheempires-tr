"""f2p.jsonl from harness result files: one line per (failing test, mutant). 'before' is the test on the unmutated
battle_engine.py (the harness only runs mutants after a passing baseline of the same tests)."""
import json
import sys

out = sys.argv[1]
seen = set()
with open(out, "w", encoding="utf-8") as f:
    for path in sys.argv[2:]:
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            for failed in r["first_failure"]:
                test = failed.split(" ", 1)[1]
                key = (test, r["id"])
                if key in seen:
                    continue
                seen.add(key)
                f.write(json.dumps({"test": test, "mutant": r["id"] + ": " + r["old"] + " -> " + r["new"],
                                    "file_line": "battle_engine.py:%d" % r["line"], "before": "passed",
                                    "after": "failed"}, ensure_ascii=False) + "\n")
print(len(seen))
