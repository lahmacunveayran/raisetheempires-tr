import json, os
here = os.path.dirname(os.path.abspath(__file__))
for f in ["slot_machine_test.py", "treasure_vault_test.py", "megaseries_test.py", "quest_trees_test.py",
          "bot_empires_test.py"]:
    p = os.path.join("test", f)
    b = open(p, "rb").read()
    open(p, "wb").write(b.replace(b"\r\n", b"\n"))
    print(f, b.count(b"\r\n"), "CRLF -> LF")
path = os.path.join(here, "f2p.jsonl")
lines = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
seen = set()
for rec in reversed(lines):
    if rec["mutant"] in seen:
        rec["note"] = ("first run: survived (equivalent for the tests then); the test was strengthened, the later "
                       "line of this mutant is the run on the final tests")
    seen.add(rec["mutant"])
open(path, "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in lines))
print(len(lines), "records,", len(seen), "mutants")
