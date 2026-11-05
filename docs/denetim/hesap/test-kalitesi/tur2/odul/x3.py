import xml.etree.ElementTree as ET
import sys
g = ET.parse(sys.argv[1] + "/gameSettings_with_fixes.xml").getroot()
items = {i.get("code"): i for i in g.iter("item") if i.get("code")}
for code in ("C001", "C000", "C003", "C004"):
    it = items[code]
    print(code, it.attrib)
    for k, isl in enumerate(it.findall("island")):
        print("   ", k, isl.get("globalIslandIndex"), isl.get("unlocks"), [r.attrib for r in isl.findall("reward")],
              [f.attrib for f in isl.findall("fleet")], [s.attrib for s in isl.findall("strength")])
for code, it in items.items():
    for k, isl in enumerate(it.findall("island")):
        if isl.findall("strength"):
            print("STR", code, k, [s.attrib for s in isl.findall("strength")], [f.attrib for f in isl.findall("fleet")])
            break
