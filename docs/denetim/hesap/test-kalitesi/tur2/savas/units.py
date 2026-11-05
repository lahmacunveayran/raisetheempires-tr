import sys
import xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
want = sys.argv[2].split(",")
for item in root.iter("item"):
    u = item.find("unit")
    if u is None or not item.get("code"):
        continue
    if item.get("code") in want or any(w == "*" + t for w in want for t in u.get("type", "").split(",")):
        print(item.get("code"), item.get("name"), item.get("subtype"), dict(u.attrib), [e.tag for e in u],
              "research:", [r.attrib for r in item.findall("upgrade")][:3])
