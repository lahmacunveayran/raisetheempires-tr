import xml.etree.ElementTree as ET
import sys
g = ET.parse(sys.argv[1] + "/gameSettings_with_fixes.xml").getroot()
items = {i.get("code"): i for i in g.iter("item") if i.get("code")}
small = []
for code, it in items.items():
    u = it.find("unit")
    if u is not None and u.get("strength") and int(u.get("strength")) <= 20:
        c = it.find("cost")
        small.append((int(u.get("strength")), code, u.get("type"), u.get("weak"), list(c.attrib) if c is not None else None))
print(sorted(small)[:30])
# island strength mults giving fractions
for code, it in items.items():
    for k, isl in enumerate(it.findall("island")):
        for s in isl.findall("strength"):
            u = items.get(s.get("code"))
            if u is None or u.find("unit") is None or not u.find("unit").get("strength"):
                continue
            v = int(u.find("unit").get("strength")) * float(s.get("mult"))
            if v != int(v):
                print("FRAC", code, k, s.attrib, u.find("unit").get("strength"), v)
                break
for code in ("N11",):
    print(code, [(c.tag, c.attrib) for c in items[code]])
for hv in g.find("combatHitValues"):
    print(hv.attrib)
for ch in g.find("combatChain"):
    print(ch.attrib)
