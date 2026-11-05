import xml.etree.ElementTree as ET
r=ET.parse("assets/29oct2012/gameSettings_with_fixes.xml").getroot()
items = {i.get("name"): i for i in r.find("items").iter("item")}
for n in ["ship20","LE_Light_Artillery_Vehicle_Red","energy06","BuildingPart48","expansionkey01","coins","oil","wood","consumable36","Gold Villain Sea 05","SF_BatRay_01"]:
    i = items[n]; print(n, {k: i.get(k) for k in ("code","type","subtype")}, [c.tag for c in i][:8])
u = [i for i in r.find("items").iter("item") if i.get("code")=="U05"][0]
print(ET.tostring(u)[:1500].decode())
print(len(r.find("items")), len(list(r.find("items").iter("item"))))
qt = r.find("questTrees"); print(len(qt), ET.tostring(qt[0])[:1500].decode())
ms = r.find("megaSeriesList"); print(len(ms), ET.tostring(ms[0])[:2500].decode())
