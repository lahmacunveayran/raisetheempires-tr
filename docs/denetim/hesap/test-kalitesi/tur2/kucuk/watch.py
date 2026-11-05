import os, sys, time
path = sys.argv[1]
seen = 0
while True:
    if os.path.exists(path):
        lines = open(path, encoding="utf-8-sig", errors="replace").read().splitlines()
        for line in lines[seen:]:
            print(line[:400], flush=True)
        seen = len(lines)
        text = "\n".join(lines)
        if '"mutant": "B4"' in text or "Traceback" in text:
            break
    time.sleep(3)
