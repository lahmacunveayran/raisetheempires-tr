import xml.etree.ElementTree as ET
r = ET.parse("assets/29oct2012/gameSettings_with_fixes.xml").getroot()
d = [t for t in r.find("questTrees").findall("questTree") if t.get("id") == "QT011"]
def norm(e):
    return (e.tag, sorted(e.attrib.items()), (e.text or "").strip(), [norm(c) for c in e])
print(norm(d[0]) == norm(d[1]))
for x, y in zip(d[0].iter(), d[1].iter()):
    if norm(x) != norm(y) and not list(x):
        print(x.tag, x.attrib, y.tag, y.attrib)
print(len(list(d[0].iter())), len(list(d[1].iter())))
