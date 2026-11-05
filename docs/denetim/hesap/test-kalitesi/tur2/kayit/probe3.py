import xml.etree.ElementTree as ET
r = ET.parse('assets/29oct2012/gameSettings_with_fixes.xml').getroot()
items = {i.get("name"): i for i in r.iter("item")}
templates = {t.get("crew"): t for t in r.find("crewTemplates")}
govt = {"Parliament": 3, "Executive Mansion": 4, "Federal Courthouse": 4, "Treasury": 5, "Maritime Academy": 6,
        "National Archives": 7, "Prison": 8, "State Media": 10, "Opera House": 11, "Mint": 12, "Intelligence HQ": 11,
        "Space Agency": 12, "Satellite_Tracking_Center": 12, "Engineering_Office": 12}
for name, n in govt.items():
    item = items.get(name)
    if item is None:
        print(name, "NO ITEM"); continue
    t = templates.get(item.get("crewTemplate"))
    print(name, n, item.get("crewTemplate"), item.get("rebuildCrewTemplate"), None if t is None else (dict(t.attrib), len(t.findall("position")), [c.tag for c in t][:3]))
    sm = item.find("stateMachineValues")
    print("   sm", None if sm is None else dict(sm.attrib))
t = list(templates.values())[0]
print(ET.tostring(t)[:600])
