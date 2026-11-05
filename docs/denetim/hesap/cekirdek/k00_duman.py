"""Duman testi: savespack kaydıyla initUser gerçek oturum katmanından (flask-session + msgspec) geçiyor mu?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz

srv, app, tmp = kur()
ids = oturumlar(app)
yaz("save.db oturumları:", len(ids))
sid = next(i for i in ids if i.startswith("session:c519d7e7"))[len("session:"):]
c = app.test_client()
c.set_cookie("session", sid)
r, body = gateway(c, [("UserService.initUser", ["", 0])])
yaz("HTTP", r.status_code, r.content_type, "cevap sayısı", len(body["data"]) if isinstance(body, dict) else body)
k = kayit(app, sid)
yaz("kayıt sonrası save_version:", k.get("save_version"), "| içeride backup zinciri:", "backup" in k)
