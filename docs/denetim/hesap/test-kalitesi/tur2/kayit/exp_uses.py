"""For each name given: every method whose code references it, with lines after each reference (how the client
compares the experiment's variant)."""
import importlib.util
import re
import sys

sys.path.insert(0, "turkce/araclar")
spec = importlib.util.spec_from_file_location("abcreader", "turkce/araclar/abc.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

abcs = mod.load("assets/ZGame.109338.swf")
texts = {}
for abc in abcs:
    for m, b in abc.bodies.items():
        texts[(id(abc), m)] = ("%s.%s" % abc.owner.get(m, ("?", "m%d" % m)), mod.disasm(abc, b))
for name in sys.argv[1:]:
    rx = re.compile(r"\b" + re.escape(name) + r"\b")
    print("=====", name)
    for owner, lines in texts.values():
        if owner == "ExperimentsManager.<cinit>":
            continue
        for i, line in enumerate(lines):
            if rx.search(line):
                print("--", owner)
                print("\n".join(lines[max(0, i - 2):i + 7]))
