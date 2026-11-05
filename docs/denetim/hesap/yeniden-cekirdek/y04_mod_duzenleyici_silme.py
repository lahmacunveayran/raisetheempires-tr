"""Yeniden denetim: mod ayar yolu (gerçek xmldiff), kayıt düzenleyici doğrulaması, silme yedeği, sürüm geçişi.

1) Depodaki gerçek active-limited-edition xmldiff'i gameSettings_with_fixes.xml'e uygulanıp /gameSettings.xml'den
   sunuluyor mu (mod etkinleştirilmiş gibi mod_engine.mod'a konur).
2) Kayıt düzenleyici POST: dict olmayan JSON, eksik quests, geçerli kayıt.
3) /wipe_session: yedek alınıyor mu, yeni oturumdan /save-editor'da görünüyor mu.
4) savespack kaydı initUser sonrası save_version.
Çalıştırma: PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y04_mod_duzenleyici_silme.py
"""
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cekirdek"))
from ortam import kur, gateway, kayit, oturumlar, yaz, sessiz

srv, app, tmp = kur()
me = srv.mod_engine
kaynak = os.path.join(srv.install_path(), "assets", "29oct2012", "gameSettings_with_fixes.xml")
diff = os.path.join(srv.install_path(), "mods", "active-limited-edition", "assets", "29oct2012",
                    "gameSettings_with_fixes.xml.xmldiff")
anahtar = "assets/29oct2012/gameSettings_with_fixes.xml"
c = app.test_client()
with sessiz():
    modsuz = c.get("/gameSettings.xml").get_data(as_text=True)
me.mod[anahtar] = me.apply_mod(lambda: me.read_file(kaynak), diff, os.path.basename(diff))
with sessiz():
    r = c.get("/gameSettings.xml")
yaz("1) gerçek xmldiff ile /gameSettings.xml -> HTTP %s, tür %s, uzunluk modsuz %d / modlu %d, farklı mı: %s" % (
    r.status_code, r.content_type, len(modsuz), len(r.get_data(as_text=True)), r.get_data(as_text=True) != modsuz))
del me.mod[anahtar]

# 2) kayıt düzenleyici
ids = [i[len("session:"):] for i in oturumlar(app)]
ben = next(i for i in ids if i.startswith("c519d7e7"))
c.set_cookie("session", ben)
gateway(c, [("UserService.initUser", ["", 0])])
for ad, govde in (("JSON liste", "[1, 2]"), ("JSON bozuk", "{"),
                  ("quests eksik", json.dumps({"user_object": kayit(app, ben)["user_object"]}))):
    with sessiz():
        r = c.post("/save-editor", data={"savegame": govde, "message": "x"})
    yaz("2) düzenleyici POST %-13s -> HTTP %s %r" % (ad, r.status_code, r.data[:30]))

# 3) silme
with sessiz():
    r = c.get("/wipe_session")
with sqlite3.connect(os.path.join(tmp, "mygames", "backups.db")) as con:
    satir = con.execute("SELECT count(*) FROM backups WHERE save_id=? AND message=?",
                        (ben, "Before deleting the save game")).fetchone()[0]
yaz("3) /wipe_session -> %s | silme öncesi yedek backups.db'de: %d | kayıt save.db'de: %s" % (
    r.status_code, satir, kayit(app, ben) is not None))
yeni = app.test_client()
with sessiz():
    sayfa = yeni.get("/save-editor").get_data(as_text=True)
yaz("   yeni oturumdan /save-editor'da 'Before deleting' yedeği görünüyor mu:", "Before deleting" in sayfa)

# 4) sürüm
diger = next(i for i in ids if i.startswith("623fecce"))
once = kayit(app, diger).get("save_version")
c2 = app.test_client()
c2.set_cookie("session", diger)
gateway(c2, [("UserService.initUser", ["", 0])])
yaz("4) save_version initUser öncesi %r -> sonrası %r (sunucu %r)" % (once, kayit(app, diger).get("save_version"),
                                                                       srv.version))
