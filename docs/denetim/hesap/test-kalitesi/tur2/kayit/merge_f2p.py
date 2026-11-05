"""Append the hand-made mutant records to f2p.jsonl. The 3 'passed' records of the first run named the wrong test for
their mutant (re-pointed and re-run in targeted2.jsonl), so they are left out; everything else goes in as it is."""
import json
import os

K = os.path.dirname(os.path.abspath(__file__))
first = [json.loads(l) for l in open(os.path.join(K, "targeted.jsonl"), encoding="utf-8")]
second = [json.loads(l) for l in open(os.path.join(K, "targeted2.jsonl"), encoding="utf-8")]
redone = {r["mutant"] for r in second}
keep = [r for r in first if not (r["mutant"] in redone and r["after"] != "failed")] + second
with open(os.path.join(K, "f2p.jsonl"), "a", encoding="utf-8") as out:
    for r in keep:
        out.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(first), len(second), len(keep), sum(r["after"] == "failed" for r in keep))
