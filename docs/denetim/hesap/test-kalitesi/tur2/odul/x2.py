import xml.etree.ElementTree as ET
import sys
base = sys.argv[1]
q = ET.parse(base + "/questSettings_with_fixes.xml").getroot()
g = ET.parse(base + "/gameSettings_with_fixes.xml").getroot()
items = {i.get("code"): i for i in g.iter("item") if i.get("code")}
for name in ("Q6016", "Q6019"):
    quest = next(x for x in q.iter("quest") if x.get("name") == name)
    for t in quest.iter("task"):
        print(name, t.attrib, [(c.tag, c.attrib) for c in t])
        if t.get("action") == "fight":
            ef = items[t.get("item")]
            print("  fleet item", ef.attrib.get("code"), [(b.tag, b.attrib) for b in ef])
# quests with battleDamage / battleKill tasks, simple ones
n = 0
for quest in q.iter("quest"):
    for t in quest.iter("task"):
        if t.get("action") in ("battleDamage", "battleKill"):
            if n < 14:
                print("BQ", quest.get("name"), len(quest.findall(".//task")), t.attrib, [(c.tag, c.attrib) for c in t])
            n += 1
print("simple battle quests", n)
# fight tasks with fleetname
m = 0
for quest in q.iter("quest"):
    for t in quest.iter("task"):
        if t.get("action") == "fight" and t.get("fleetname"):
            if m < 5:
                print("FN", quest.get("name"), t.attrib, [(c.tag, c.attrib) for c in t])
            m += 1
print("fight tasks with fleetname", m)
# islands
print("MAPS", [c for c, it in items.items() if it.findall("island")][:60])
for code in ("C001", "C037"):
    mp = items[code]
    for k, isl in enumerate(mp.findall("island")):
        rw = [r.attrib for r in isl.findall("reward")]
        print(code, k, isl.get("globalIslandIndex"), isl.get("unlocks"), rw, [s.attrib for s in isl.findall("strength")][:3])
hundred = []
withitem = []
for code, it in items.items():
    if it.get("type") == "map" or it.findall("island"):
        for k, isl in enumerate(it.findall("island")):
            for r in isl.findall("reward"):
                if r.get("count") == "100":
                    hundred.append((code, k, r.attrib))
                if r.get("type") == "item":
                    withitem.append((code, k, r.attrib))
print("count 100", hundred[:10])
print("item", withitem[:10])
# strength upgrades
for code, it in items.items():
    mod = it.find("modifier")
    if mod is not None and mod.get("strength"):
        print("UPG", code, it.get("name"), mod.attrib)
        break
for code in ("U01", "U05", "U04", "V61", "PU5", "SK4", "U58", "SU02", "U63", "UB96", "ML11"):
    it = items[code]
    print("UNIT", code, it.find("unit").attrib, it.find("cost").attrib if it.find("cost") is not None else None)
