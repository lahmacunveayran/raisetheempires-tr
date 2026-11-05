import json,sys
d=json.load(open(sys.argv[1]))
tb=tc=ts=tcs=0
for f,v in sorted(d["files"].items()):
    s=v["summary"]
    if f.startswith("turkce"): continue
    nb=s["num_branches"]; cb=s["covered_branches"]
    tb+=nb; tc+=cb; ts+=s["num_statements"]; tcs+=s["covered_lines"]
    print(f"{f:22s} stmts {s['covered_lines']:4d}/{s['num_statements']:4d} ({100*s['covered_lines']/max(1,s['num_statements']):5.1f}%)  branches {cb:4d}/{nb:4d} ({100*cb/max(1,nb):5.1f}%)")
print(f"TOTAL stmts {tcs}/{ts} ({100*tcs/ts:.1f}%) branches {tc}/{tb} ({100*tc/tb:.1f}%)")
