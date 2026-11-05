import json
R = r"<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad\fix2\sunucu"
res = json.load(open(R + r"\mutants_result.json", encoding="utf-8"))
res.update(json.load(open(R + r"\mutants_result2.json", encoding="utf-8")))
out = open(R + r"\f2p.jsonl", "w", encoding="utf-8")
for mid, r in res.items():
    out.write(json.dumps({"test": r.get("detail", "").replace("FAILED ", "").split(" - ")[0] if r["status"] != "survived" else "-",
                          "mutant": mid + ": " + r["desc"], "file": "empires-server.py",
                          "before": "pass (unmutated)", "after": r["status"]}, ensure_ascii=False) + "\n")
extra = [
    {"test": "whole suite, shuffled (denetim2_shuffle) SHUFFLE_SEED=11/22/33",
     "mutant": "B-O1: cb00c06 test/conftest.py + test/session_layer_test.py (module fixture doing db.init_app again)",
     "file": "test/session_layer_test.py:32-42 (cb00c06)", "before": "202 passed 28 errors / 202+28 / 203+27",
     "after": "fixed code: 258 passed for 11, 22, 33 and reverse"},
    {"test": "conftest.py pytest_sessionfinish repo check (run: test/battle_test.py)",
     "mutant": "B-D1: log redirect removed (daiquiri.output._get_log_file_path not patched)",
     "file": "test/conftest.py", "before": "exit 0, no leak reported", "after": "exit 1: 'The tests changed files in the repository folder: log.txt'"},
    {"test": "conftest.py pytest_sessionfinish repo check (run: test/battle_test.py)",
     "mutant": "B-D1: init_settings.caching = False removed", "file": "test/conftest.py",
     "before": "exit 0", "after": "exit 1: cache/directory.cache, cache/mods.config.cache"},
]
for e in extra:
    out.write(json.dumps(e, ensure_ascii=False) + "\n")
print(len(res) + len(extra))
