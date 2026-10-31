"""CEK: gameSettings/questSettings yolları mod varsa çöker: send_from_directory_mod mod için bytes döndürür,
görünüm ise Response bekleyip .direct_passthrough atar. (flashFile bu durumu ele alıyor, bu ikisi almıyor.)
Ayrıca örnek mod (active-limited-edition) gameSettings.xml'i değiştirir; sunucu ise gameSettings_with_fixes.xml sunar."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, yaz, sessiz, hatalar

srv, app, tmp = kur(savespack=False)
c = app.test_client()
for yol, dosya in (("/gameSettings.xml", "assets/29oct2012/gameSettings_with_fixes.xml"),
                   ("/127.0.0.1questSettings.xml", "assets/29oct2012/questSettings_with_fixes.xml")):
    with sessiz():
        r0 = c.get(yol)
    srv.mod_engine.mod[dosya] = lambda: b"<settings/>"   # mods.conf'ta 'gameRevision_...' = true olunca olan
    with sessiz():
        r1 = c.get(yol)
    del srv.mod_engine.mod[dosya]
    yaz("%-28s modsuz -> %s | mod etkin -> %s %r" % (yol, r0.status_code, r1.status_code, r1.data[:15]))
for h in hatalar(tmp)[-1:]:
    yaz("  log.txt:", h)
mods = os.path.join(srv.install_path(), "mods")
for root, _, files in os.walk(mods):
    for f in files:
        if "ettings" in f and f.endswith((".xml", ".xmldiff")):
            yaz("  mod dosyası:", os.path.relpath(os.path.join(root, f), mods))
