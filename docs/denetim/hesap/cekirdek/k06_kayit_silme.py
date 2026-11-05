"""CEK: /wipe_session kaydı save.db'den kalıcı olarak siler; önce yedek almaz, yedekler de artık ulaşılamaz olur."""
import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz, sessiz

srv, app, tmp = kur()
ben = next(i for i in oturumlar(app) if i.startswith("session:c519d7e7"))[len("session:"):]
c = app.test_client()
c.set_cookie("session", ben)
gateway(c, [("UserService.initUser", ["", 0])])  # eski iç yedek zinciri backups.db'ye taşınır
with sessiz():
    srv_backups = srv.list_backups({"session_id": "session:" + ben})
yaz("silmeden önce: save.db'de kayıt var mı:", kayit(app, ben) is not None, "| backups.db'de bu kaydın yedeği:", len(srv_backups))
with sessiz():
    r = c.get("/wipe_session")  # GET; Origin/Referer yoksa engellenmez
yaz("GET /wipe_session ->", r.status_code, r.headers.get("Location"))
yaz("sonra: save.db'de kayıt var mı:", kayit(app, ben) is not None)
con = sqlite3.connect(os.path.join(tmp, "mygames", "backups.db"))
yaz("backups.db'de hâlâ duran yedek:", con.execute("select count(*) from backups where save_id=?", (ben,)).fetchone()[0])
with sessiz():
    r = c.get("/save-editor")
yaz("yeni oturumla /save-editor ->", r.status_code, r.data[:30])
