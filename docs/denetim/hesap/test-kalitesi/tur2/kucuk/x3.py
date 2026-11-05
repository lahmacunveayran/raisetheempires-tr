import xml.etree.ElementTree as ET
r=ET.parse("assets/29oct2012/gameSettings_with_fixes.xml").getroot()
qt = r.find("questTrees")
ids = [t.get("id") for t in qt]
print("dupe ids", [i for i in set(ids) if ids.count(i) > 1])
n_pre = 0
for t in qt:
    nodes = [n for n in t.findall("node") if n.get("quest")]
    pre = [n for n in nodes if n.get("prequel")]
    n_pre += len(pre)
    roots = [n.get("quest") for n in nodes if not n.get("prequel")]
    if roots and roots[0] != nodes[0].get("quest"):
        print("tree", t.get("id"), "first root", roots[0], "first node", nodes[0].get("quest"))
print("nodes with prequel", n_pre)
for t in qt:
    if t.get("id") in ("QT01","QT02"):
        print(t.get("id"), [(n.get("quest"), n.get("prequel")) for n in t.findall("node")][:6], t.get("rewardQuest"), t.find("criteria/level").attrib, t.find("hook").attrib, t.get("totalQuestTreeAllies"))
import sys; sys.path.insert(0, ".")
