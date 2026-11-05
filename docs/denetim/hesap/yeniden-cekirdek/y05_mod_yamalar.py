"""Yeniden denetim: bir xmldiff modu etkinken sunucunun kendi gameSettings yamaları (event_buildings,
quest_trees) hâlâ uygulanıyor mu? Bu yamalar metin araması yapıyor ('<item name="..."', '<questTree id="..."');
xmldiff ise XML'i yeniden yazıyor.
Çalıştırma: PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y05_mod_yamalar.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cekirdek"))
from ortam import kur, yaz, sessiz

srv, app, tmp = kur(savespack=False)
me, eb, qt = srv.mod_engine, srv.event_buildings, srv.quest_trees
kaynak = os.path.join(srv.install_path(), "assets", "29oct2012", "gameSettings_with_fixes.xml")
diff = os.path.join(srv.install_path(), "mods", "active-limited-edition", "assets", "29oct2012",
                    "gameSettings_with_fixes.xml.xmldiff")
ham = me.read_file(kaynak).decode("utf-8")
with sessiz():
    modlu = me.apply_mod(lambda: me.read_file(kaynak), diff, os.path.basename(diff))()
modlu = modlu.decode("utf-8") if isinstance(modlu, bytes) else modlu
yaz("ham ilk 120 karakter :", repr(ham[:120]))
yaz("modlu ilk 120 karakter:", repr(modlu[:120]))
for ad, metin in (("modsuz", ham), ("modlu ", modlu)):
    with sessiz():
        e = eb.patch_settings_xml(metin, eb.served_event())
        q = qt.patch_settings_xml(metin, [(10, 10), (12, 12)])
    yaz("%s: event_buildings yaması değiştirdi mi: %-5s (+%d karakter) | quest_trees yaması değiştirdi mi: %-5s" % (
        ad, e != metin, len(e) - len(metin), q != metin))
ornek = next((ev for ev in eb.EVENTS if ev.get("code")), None)
if ornek:
    yaz("örnek: '<item name=\"%s\"' modsuzda: %s, modluda: %s" % (
        ornek["code"], ('<item name="%s"' % ornek["code"]) in ham, ('<item name="%s"' % ornek["code"]) in modlu))
