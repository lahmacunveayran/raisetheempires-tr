"""CEK: bir çağrı hata verince ne olur? (gerçek oturum katmanı, savespack kaydı)

1) 'list' adımı yok olan nesne için: sunucunun kendi "çökmesin" korumasının döndürdüğü data=[] cevabı
   report_world_log içinde IndexError verir.
2) Envanterde olmayan bir eşya için UserService.useItem -> KeyError.
3) Aynı paketteki sağlam çağrı (setWorldName) da geri alınır; cevap AMF değil, HTTP 200 'It went wrong'.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz

srv, app, tmp = kur()
sid = next(i for i in oturumlar(app) if i.startswith("session:c519d7e7"))[len("session:"):]
c = app.test_client()
c.set_cookie("session", sid)
gateway(c, [("UserService.initUser", ["", 0])])
eski_ad = kayit(app, sid)["user_object"]["userInfo"]["worldName"]

yok = 987654321
for adim in ("list", "remove", "move"):
    r, body = gateway(c, [("WorldService.performAction",
                           [adim, {"id": yok, "position": "1,1,0", "itemName": "Market"}, []])])
    yaz("performAction %-6s yok nesne -> HTTP %s %s | %s" % (adim, r.status_code, r.content_type,
        body if isinstance(body, str) else "AMF, %d cevap" % len(body["data"])))

r, body = gateway(c, [("UserService.setWorldName", ["YeniAd"]), ("UserService.useItem", ["OLMAYAN_ESYA"])])
yaz("setWorldName + useItem(olmayan) -> HTTP", r.status_code, r.content_type, "|", body)
yaz("kayıttaki dünya adı:", repr(kayit(app, sid)["user_object"]["userInfo"]["worldName"]), "(önce:", repr(eski_ad) + ")")

from ortam import hatalar
for h in hatalar(tmp):
    yaz("  log.txt:", h)
