"""Drop the server mutant results that are errors of 0 s (the worktree was removed under the run), to run them again."""
import json, os
K = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(K, "remut_server_save.json")
d = json.load(open(path, encoding="utf-8"))
d = {k: r for k, r in d.items() if not (r["now"] == "error" and r["seconds"] < 1)}
json.dump(d, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(d))
