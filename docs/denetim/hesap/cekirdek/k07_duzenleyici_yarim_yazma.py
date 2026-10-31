"""CEK: kayıt düzenleyicide (POST /save-editor) eksik anahtarlı JSON kaydı yarım yazar; geçersiz kayıt da denetimsiz
kabul edilir. save_savegame transactional_session ile sarılı değil."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, yaz, sessiz

srv, app, tmp = kur(savespack=False)
c = app.test_client()
gateway(c, [("UserService.initUser", ["", 0])])
sid = c.get_cookie("session").value
k = kayit(app, sid)
uo = k["user_object"]
uo["userInfo"]["worldName"] = "YARIM"
with sessiz():
    r = c.post("/save-editor", data={"savegame": json.dumps({"user_object": uo}), "message": "deneme"})  # 'quests' yok
k2 = kayit(app, sid)
yaz("eksik 'quests' -> HTTP", r.status_code, r.data[:20], "| kayıttaki ad:", k2["user_object"]["userInfo"]["worldName"],
    "| quests hâlâ eski mi:", k2["quests"] == k["quests"])

with sessiz():
    r = c.post("/save-editor", data={"savegame": json.dumps({"user_object": {"bozuk": 1}, "quests": [], "battle": None,
                                                           "fleets": {}, "population": 0}), "message": "x"})
k3 = kayit(app, sid)
yaz("geçersiz user_object -> HTTP", r.status_code, r.headers.get("Location"), "| validate_save:", srv.validate_save(k3))
