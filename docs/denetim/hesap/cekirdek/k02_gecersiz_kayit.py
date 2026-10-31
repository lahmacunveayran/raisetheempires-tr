"""CEK: initUser geçersiz kayıtta cevap vermeden geçiyor -> cevap sayısı istek sayısından az.

İstemci (TransactionManager.onAmfBatchComplete) `data.length == m_batchedAmfCalls.length` denetler; eşit değilse
yalnızca 'ERROR - batch results is not an array of length' yazar, hiçbir çağrının onSuccess'i çalışmaz.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, yaz, sessiz

srv, app, tmp = kur(savespack=False)
c = app.test_client()
r, body = gateway(c, [("UserService.initUser", ["", 0])])  # yeni oyun
sid = c.get_cookie("session").value
with sessiz():
    p = c.get("/patch/user_object/userInfo/player/level/string/onbes")  # kayıt düzenleyicinin yaptığı türden bir bozulma
yaz("patch ->", p.status_code, "| level:", repr(kayit(app, sid)["user_object"]["userInfo"]["player"]["level"]))
r, body = gateway(c, [("UserService.initUser", ["", 0]), ("UserService.setSeenFlag", ["x"])])
yaz("2 çağrı gönderildi -> HTTP", r.status_code, r.content_type, "| cevap sayısı:", len(body["data"]))
