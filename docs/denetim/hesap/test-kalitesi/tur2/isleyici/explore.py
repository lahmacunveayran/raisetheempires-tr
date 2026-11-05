import json
import xml.etree.ElementTree as ET
d = json.load(open('test/init_user.json'))
p = d['userInfo']['player']
print(p['expansions'], p['cash'], p['level'], p['inventory'])
print(d['userInfo']['world']['resources'], d['userInfo']['world'].get('resourceOrder'))
print(sorted(d.keys())); print(sorted(p.keys())); print(d.get('pvp'), d.get('visitorHelpRequests'))
root = ET.parse('assets/29oct2012/gameSettings_with_fixes.xml').getroot()
gs = root.find('gamesettings'); print({k: v for k, v in gs.attrib.items() if 'ontract' in k or 'xpansion' in k.lower()})
items = root.find('items').findall('item')
print(len(items))
exp = [i for i in items if i.get('subtype') == 'expansion']
print(len(exp))
for i in exp[:4]:
    print(ET.tostring(i)[:400])
en = [i for i in items if i.find('energyYield') is not None or i.get('energyYield')]
print(len(en))
for i in en[:3]:
    print(ET.tostring(i)[:500])
mk = [i for i in items if 'arket' in (i.get('name') or '')]
for i in mk[:4]:
    print(ET.tostring(i)[:300])
