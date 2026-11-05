"""CEK: saved_on (ya da replaced_on) alanı boş olan bir yedek, kayıt düzenleyici sayfasını (yedekten geri yükleme
ekranını) tamamen çökertir: format_backup_message -> datetime.fromtimestamp(None)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz, sessiz

srv, app, tmp = kur()
for sid in [i[len("session:"):] for i in oturumlar(app)]:
    k = kayit(app, sid)
    n, node, bos = 0, k, 0
    while isinstance(node.get("backup"), dict):
        node = node["backup"]; n += 1
        bos += node.get("saved_on") is None or node.get("replaced_on") is None
    if n:
        yaz("savespack", sid[:8], "iç yedek zinciri:", n, "| saved_on/replaced_on eksik olan:", bos, "| kaydın kendi saved_on'u:", k.get("saved_on"))

c = app.test_client()
gateway(c, [("UserService.initUser", ["", 0])])  # yeni oyun
sid = c.get_cookie("session").value
with sessiz():
    r = c.get("/save-editor")
yaz("yeni oyun, /save-editor ->", r.status_code)
# Eski bir sürümden gelen, saved_on'u olmayan kayıt: ilk create_backup'ta yedeğin saved_on'u NULL olur
with app.test_request_context():
    import flask
    flask.session.sid = sid
    flask.session.update({k: v for k, v in kayit(app, sid).items() if k != "saved_on"})
    with sessiz():
        srv.create_backup("eski sürüm kaydı")
with sessiz():
    r = c.get("/save-editor")
yaz("saved_on'suz yedek eklendikten sonra /save-editor ->", r.status_code, r.data[:20])
try:
    srv.format_backup_message({"saved_on": None, "replaced_on": 1.0})
except Exception as e:
    yaz("format_backup_message({'saved_on': None}) ->", type(e).__name__, e)
