"""Read ExperimentsManager.<cinit> (abc.py method dump): constant name -> value, and print, for each experiment
of the migration steps, the constants defined right after it (its variants)."""
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read().splitlines()
props = []  # (name, value) in order
value = None
for line in text:
    m = re.match(r"\s*\d+ (pushstring|pushbyte|pushshort|pushint|pushtrue|pushfalse)\s*(.*)", line)
    if m:
        value = m.group(2)
        continue
    m = re.match(r"\s*\d+ initproperty (\S+)", line)
    if m:
        props.append((m.group(1), value))
        value = None
WANTED = sys.argv[2].split(",")
for i, (name, v) in enumerate(props):
    if v and v.strip("'") in WANTED:
        after = []
        for n2, v2 in props[i + 1:i + 8]:
            if v2 and v2.startswith("'"):
                break
            after.append((n2, v2))
        print(v, name, after)
found = {v.strip("'") for _, v in props if v}
print("not in ExperimentsManager:", [w for w in WANTED if w not in found])
