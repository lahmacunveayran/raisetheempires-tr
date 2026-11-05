import json, os
K = os.path.dirname(os.path.abspath(__file__))
for n in ("save_engine", "save_migration"):
    d = json.load(open(os.path.join(K, "remut_%s.json" % n), encoding="utf-8"))
    for k, r in sorted(d.items(), key=lambda kv: int(kv[0])):
        if r["now"] == "survived":
            print(n, k, r["line"], "|", r["original"][:70], "=>", r["mutant"][:70])
