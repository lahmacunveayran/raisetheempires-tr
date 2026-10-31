"""CEK: RequestService.crewRequest yalnızca allies/ klasöründeki hazır komşuları tanır (allies[str(f)]).
Arkadaş listesi ise diğer yerel kayıtları da içerir (get_sessions_friends). Yerel bir kayıttan ekip istemek KeyError."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz, hatalar

srv, app, tmp = kur()
ids = [i[len("session:"):] for i in oturumlar(app)]
ben = next(i for i in ids if i.startswith("c519d7e7"))
komsu_uid = kayit(app, next(i for i in ids if i.startswith("623fecce")))["user_object"]["userInfo"]["player"]["uid"]
c = app.test_client()
c.set_cookie("session", ben)
gateway(c, [("UserService.initUser", ["", 0])])
w = kayit(app, ben)["user_object"]["userInfo"]["world"]
bina = next(o for o in w["objects"] if o["itemName"] == "Parliament")
hazir = next(k for k, a in srv.allies.items() if a.get("neighbor"))
for f in (int(hazir), komsu_uid):
    r, body = gateway(c, [("RequestService.crewRequest", [[f], bina["id"], "Parliament", "crew"])])
    yaz("crewRequest arkadaş %s (%s) -> HTTP %s %s" % (f, "allies/ komşusu" if str(f) in srv.allies else "yerel kayıt",
        r.status_code, "AMF" if r.content_type == "application/x-amf" else r.data[:15]))
for h in hatalar(tmp)[-1:]:
    yaz("  log.txt:", h)
