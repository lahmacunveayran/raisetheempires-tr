import json, collections, os
K = os.path.dirname(os.path.abspath(__file__))
for n in ("save_engine", "save_migration", "server_save"):
    d = json.load(open(os.path.join(K, "remut_%s.json" % n), encoding="utf-8"))
    print(n, len(d), collections.Counter(r["now"] for r in d.values()))
    for k, r in d.items():
        if r["now"] in ("error", "timeout") or r["seconds"] < 3:
            print("  ", k, r["line"], r["now"], r["seconds"], r["detail"][:150].replace("\n", " "))
