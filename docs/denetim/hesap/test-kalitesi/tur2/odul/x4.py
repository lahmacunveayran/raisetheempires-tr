import xml.etree.ElementTree as ET
import sys
g = ET.parse(sys.argv[1] + "/gameSettings_with_fixes.xml").getroot()
q = ET.parse(sys.argv[1] + "/questSettings_with_fixes.xml").getroot()
items = {i.get("code"): i for i in g.iter("item") if i.get("code")}
for code in ("N04", "N75", "N80", "U44", "V06", "UN33", "UL61", "U58", "SU02", "U63", "UB96", "U92", "V61", "U43"):
    it = items[code]
    print(code, it.get("type"), it.get("subtype"), it.get("unitClass"), [(c.tag, c.attrib) for c in it if c.tag in ("unit", "consumable", "cost")])
for code in ("XD05", "XT05", "XA05", "XC05", "XR05", "XS05", "XS01", "XS02", "XS03", "XS04"):
    it = items.get(code)
    if it is not None:
        print(code, it.get("name"), [(c.tag, c.attrib) for c in it if c.tag == "modifier"])
n = 0
for code, it in items.items():
    c = it.find("consumable")
    if c is not None and c.get("target") == "enemy" and not c.get("di") and c.get("type") != "all" and it.get("subtype") == "consumable":
        if n < 8:
            print("NODMG", code, it.get("name"), dict(c.attrib), it.get("subtype"))
        n += 1
for name in ("QW202", "QW192", "QW212", "QW190", "QW228"):
    quest = next(x for x in q.iter("quest") if x.get("name") == name)
    print(name, [(t.attrib.get("action"), t.attrib.get("total"), t.attrib.get("item"), t.attrib.get("fleetname"), [(c.tag, c.attrib) for c in t if c.tag in ("targetInfo", "fleet")]) for t in quest.iter("task")])
    for t in quest.iter("task"):
        if t.get("action") == "fight":
            ef = items[t.get("item")]
            print("  fleet", ef.get("code"), [(b.tag, b.attrib) for b in ef])
