"""Counts of the audit's save mutants now, and f2p lines for each survivor the new tests kill.
Score as the audit: killed / (sample - equivalent); equivalents are the audit's E list (mut_survivors.txt)."""
import json
import os
import re

K = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(K, "..", "..", "denetim2")
SECTIONS = {"save_engine": "mut_save_engine.json", "save_migration": "mut_save_migration.json",
            "server_save": "mut_server_save.json"}

# the audit's classification, in the order of the survivors (same order as its JSON keys sorted)
text = open(os.path.join(D, "mut_survivors.txt"), encoding="utf-8").read()
blocks = re.split(r"\n(?=mut_\w+\.json)", text)
classes = {}
for block in blocks:
    m = re.match(r"(mut_\w+\.json)", block)
    if m:
        classes[m.group(1)] = re.findall(r"^   (E|G|K2)  line\s+(\d+)", block, re.M)

f2p = open(os.path.join(K, "f2p.jsonl"), "a", encoding="utf-8")
for name, audit_file in SECTIONS.items():
    audit = json.load(open(os.path.join(D, audit_file), encoding="utf-8"))["results"]
    now = json.load(open(os.path.join(K, "remut_%s.json" % name), encoding="utf-8"))
    survivors = [k for k, r in sorted(audit.items(), key=lambda kv: int(kv[0]))
                 if r.get("full_status", r["status"]) == "survived"]
    cls = classes[audit_file]
    assert len(cls) == len(survivors), (name, len(cls), len(survivors))
    eq = {k for k, (c, line) in zip(survivors, cls) if c == "E"}
    for k, (c, line) in zip(survivors, cls):
        assert int(line) == audit[k]["line"], (name, k, line, audit[k]["line"])
    sample = len(audit)
    k2 = set()  # K2 lines of the audit are gaps too (all its survivors here are full-suite survivors)
    killed_before = sample - len(survivors) + len(k2)
    survivors = [k for k in survivors if k not in k2]
    newly = [k for k in survivors if now[k]["now"] in ("killed", "timeout", "error")]
    left = [k for k in survivors if now[k]["now"] == "survived"]
    print(name, "sample", sample, "equivalent", len(eq), "killed by the audit's tests", killed_before,
          "now killed besides", len(newly), "-> score %d/%d = %.1f%%" % (
              killed_before + len(newly), sample - len(eq), 100 * (killed_before + len(newly)) / (sample - len(eq))))
    for k in left:
        print("   left", "E" if k in eq else "G", "line", now[k]["line"], now[k]["original"][:60], "->",
              now[k]["mutant"][:60])
    for k in newly:
        if k in eq:
            print("   NOTE killed an 'equivalent'", k, now[k]["line"], now[k]["detail"][:100])
        f2p.write(json.dumps({"test": now[k]["detail"].replace("FAILED ", "").split(" - ")[0],
                              "mutant": "%s -> %s" % (now[k]["original"], now[k]["mutant"]),
                              "where": "%s:%d" % ({"server_save": "empires-server.py"}.get(name, name + ".py"),
                                                  now[k]["line"]),
                              "before": "survived (audit denetim2, old tests)", "after": now[k]["now"],
                              "source": "audit mutant %s #%s" % (audit_file, k)}, ensure_ascii=False) + "\n")
