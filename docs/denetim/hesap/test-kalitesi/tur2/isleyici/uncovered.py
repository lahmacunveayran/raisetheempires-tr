"""Lists functions of empires-server.py with no covered line, and the branch total, from a coverage JSON."""
import json, sys
d = json.load(open(sys.argv[1]))
f = [v for k, v in d["files"].items() if k.endswith("empires-server.py")][0]
print("branches", f["summary"].get("covered_branches"), "/", f["summary"].get("num_branches"),
      "lines", f["summary"]["covered_lines"], "/", f["summary"]["num_statements"])
for name, v in f.get("functions", {}).items():
    s = v["summary"]
    if s["covered_lines"] == 0 and s["num_statements"] > 0:
        print("0", name, s["num_statements"])
