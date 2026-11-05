import xml.etree.ElementTree as ET
r=ET.parse("assets/29oct2012/gameSettings_with_fixes.xml").getroot()
items = {i.get("name"): i for i in r.find("items").iter("item")}
print(len(items), len(list(r.find("items").iter("item"))))
by_code = {}
for i in r.find("items").iter("item"):
    by_code.setdefault(i.get("code"), []).append(i.get("name"))
for c in ["U63","UA19","UA33","U59","UL02","US24","UG15","EN6","B48","N36","N37","xk01"]:
    print(c, by_code.get(c))
for n in ["ship19","LE_SikX2","LE_Fokker"]:
    print(n, items[n].get("code"), items[n].get("type"))
print([ (k, v) for k, v in by_code.items() if len(v) > 1][:10])
