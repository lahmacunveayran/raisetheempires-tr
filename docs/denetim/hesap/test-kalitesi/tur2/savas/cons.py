import sys
import xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
keys = ("dot", "attack", "defend", "shield", "damage", "chipFactor", "percent")
for item in root.iter("item"):
    c = item.find("consumable")
    if c is None:
        continue
    if any(k in c.attrib for k in keys) or c.findall("against"):
        print(item.get("code"), item.get("name"), item.get("subtype"), dict(c.attrib),
              [dict(a.attrib) for a in c.findall("against")])
print("--- upgrades")
for item in root.iter("item"):
    m = item.find("modifier")
    if m is not None and item.get("type") == "upgrade" or (m is not None and ("accuracy" in m.attrib or "dodge" in m.attrib)):
        if "accuracy" in m.attrib or "dodge" in m.attrib or "damage" in m.attrib:
            print(item.get("code"), item.get("name"), dict(m.attrib))
print("--- weaker")
for item in root.iter("item"):
    u = item.find("unit")
    if u is not None and ("weaker" in u.attrib or "weaker" in item.attrib):
        print(item.get("code"), item.get("name"), dict(u.attrib))
