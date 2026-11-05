"""CEK: aynı paket içinde başka bir kayda (komşu) yazılan değişiklik, paket başarısız olunca geri alınmaz.

VisitorService.help komşunun kaydına store_session ile hemen (pickle olarak) yazar. Paketteki sonraki çağrı hata
verirse oyuncunun kaydı geri alınır ama komşununki alınmaz. İstemci aynı paketi yeniden dener -> her denemede
komşunun visitorHelpRequests listesine aynı nesne bir kez daha eklenir.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz

srv, app, tmp = kur()
ids = [i[len("session:"):] for i in oturumlar(app)]
ben = next(i for i in ids if i.startswith("c519d7e7"))
komsu = next(i for i in ids if i.startswith("623fecce"))
k = kayit(app, komsu)
komsu_uid = k["user_object"]["userInfo"]["player"]["uid"]
nesne = next(o for o in k["user_object"]["userInfo"]["world"]["objects"] if o["itemName"].startswith("tree"))
c = app.test_client()
c.set_cookie("session", ben)
gateway(c, [("UserService.initUser", ["", 0])])
benim_uid = kayit(app, ben)["user_object"]["userInfo"]["player"]["uid"]
yaz("komşu uid", komsu_uid, "nesne", nesne["id"], nesne["itemName"], "| benim uid", benim_uid)
for deneme in range(1, 4):  # istemcinin yeniden denemesi: aynı paket
    r, body = gateway(c, [("VisitorService.help", [komsu_uid, nesne["id"], "clear"]),
                          ("UserService.useItem", ["OLMAYAN_ESYA"])])
    k = kayit(app, komsu)
    yaz("deneme %d -> HTTP %s %s | komşudaki visitorHelpRequests[%s] = %r" % (
        deneme, r.status_code, "AMF" if r.content_type == "application/x-amf" else r.data[:20],
        benim_uid, (k["user_object"].get("visitorHelpRequests") or {}).get(str(benim_uid))))
with app.app_context():
    rec = app.session_interface.sql_session_model.query.filter_by(session_id="session:" + komsu).first()
    yaz("komşu kaydının ilk baytı:", bytes(rec.data)[:2], "(0x80 = pickle; flask-session msgpack yazar)")
