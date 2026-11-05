import xml.etree.ElementTree as ET
import sys
root = ET.parse(sys.argv[1]).getroot()
gs = root.find("gamesettings").attrib
for k, v in gs.items():
    if "ombat" in k or "eplay" in k:
        print(k, v)
for hit in root.find("combatRewards"):
    print(hit.tag, [r.attrib for r in hit])
# chip consumables
for item in root.iter("item"):
    c = item.find("consumable")
    if c is not None and c.get("chipFactor"):
        print("CHIP", item.get("code"), item.get("name"), dict(c.attrib), [a.attrib for a in c.findall("against")])
# units by rare cost
seen = {}
for item in root.iter("item"):
    u = item.find("unit")
    cost = item.find("cost")
    if u is None or cost is None:
        continue
    rares = [k for k in cost.attrib if k == "rare" or k.startswith("nrare")]
    if rares:
        key = rares[0]
        seen.setdefault(key, []).append((item.get("code"), u.get("strength"), u.get("type"), list(cost.attrib)))
for k, v in seen.items():
    print("RARE", k, len(v), v[:4])
