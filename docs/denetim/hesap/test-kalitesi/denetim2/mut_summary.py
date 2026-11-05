"""Summarises the mutation results of mut_harness.py: score on the sample, 95% Wilson interval, the estimate for all
mutants of the file (mutants on lines the suite never runs cannot be killed), and the list of survivors.
Usage: python mut_summary.py mut_battle_engine.json [more.json ...] [--survivors]
"""
import json
import math
import sys


def wilson(k, n, z=1.96):
    if n == 0:
        return 0, 0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d


show = "--survivors" in sys.argv
for path in [a for a in sys.argv[1:] if not a.startswith("--")]:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    meta, res = d["meta"], d["results"]
    st = [r["status"] for r in res.values()]
    killed = sum(s in ("killed", "error", "timeout") for s in st)
    n = len(st)
    lo, hi = wilson(killed, n)
    share = meta["on_covered_lines"] / meta["total_mutants"]
    print("== %s: %d of %d sampled mutants done (sample of %d, %d mutants in all, %d on lines the suite runs)"
          % (meta["file"], n, meta["sample"], meta["sample"], meta["total_mutants"], meta["on_covered_lines"]))
    print("   killed %d (tests failed %d, import/collection error %d, timeout %d), survived %d"
          % (killed, st.count("killed"), st.count("error"), st.count("timeout"), st.count("survived")))
    print("   score on mutants of run lines: %.1f%% (95%% CI %.1f-%.1f%%)" % (100 * killed / n, 100 * lo, 100 * hi))
    print("   estimated score on all mutants of the scope: %.1f%% (95%% CI %.1f-%.1f%%)"
          % (100 * killed / n * share, 100 * lo * share, 100 * hi * share))
    if show:
        for k, r in sorted(res.items(), key=lambda kv: kv[1]["line"]):
            if r["status"] == "survived":
                print("   S line %4d: %s\n              -> %s" % (r["line"], r["original"][:110], r["mutant"][:110]))
