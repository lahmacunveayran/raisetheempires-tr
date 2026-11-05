import xml.etree.ElementTree as ET
r=ET.parse("assets/29oct2012/gameSettings_with_fixes.xml").getroot()
for tag in ["slotMachineFeatured","treasureVaultCosts"]:
    e=r.find(tag); print(ET.tostring(e)[:3000].decode())
g=r.find("gamesettings")
print({k:v for k,v in g.attrib.items() if "Slot" in k or "Vault" in k or "vault" in k})
for t in r.iter():
    if "vault" in t.tag.lower() or "loot" in t.tag.lower(): print(t.tag, t.attrib)
