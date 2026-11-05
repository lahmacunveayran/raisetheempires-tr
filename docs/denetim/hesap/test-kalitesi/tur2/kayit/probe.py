import xml.etree.ElementTree as ET
r = ET.parse('assets/29oct2012/gameSettings_with_fixes.xml').getroot()
ms = r.find('megaSeriesList')
print(ms.attrib, len(ms))
for s in ms:
    print(s.tag, s.attrib)
    for c in s:
        print('  ', c.tag, c.attrib, [(n.tag, n.attrib) for n in c][:3], len(c))
    break
print([s.get('id') for s in ms])
sm = r.find('slotMachineFeatured')
for s in sm:
    print(s.tag, s.attrib)
    for c in s:
        print('  ', c.tag, c.attrib)
