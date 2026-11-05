"""Yeniden denetim: çağrı başına koruma (guarded_call) ve başka kayda ertelenmiş yazım (defer_save_writes).

1) VisitorService.help'in kendisi store_session'dan SONRA patlarsa (click_next_state hatası) komşunun kaydına
   yazılmamalı, oyuncunun kaydı da geri alınmalı; sağlam help ise komşuya yazmalı.
2) Çağrı başına anlık görüntünün maliyeti: seviye 85 kayıtta (savespack 623fecce) 1, 10 ve 30 çağrılık paket.
Çalıştırma: PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y03_cagri_koruma.py
"""
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cekirdek"))
from ortam import kur, gateway, kayit, oturumlar, yaz

srv, app, tmp = kur()
ids = [i[len("session:"):] for i in oturumlar(app)]
ben = next(i for i in ids if i.startswith("c519d7e7"))
komsu = next(i for i in ids if i.startswith("623fecce"))
k = kayit(app, komsu)
komsu_uid = k["user_object"]["userInfo"]["player"]["uid"]
agaclar = [o for o in k["user_object"]["userInfo"]["world"]["objects"] if o["itemName"].startswith("tree")]
c = app.test_client()
c.set_cookie("session", ben)
gateway(c, [("UserService.initUser", ["", 0])])
benim_uid = str(kayit(app, ben)["user_object"]["userInfo"]["player"]["uid"])


def yardimlar():
    return (kayit(app, komsu)["user_object"].get("visitorHelpRequests") or {}).get(benim_uid)


asil = srv.click_next_state


def patlayan(*a, **kw):
    raise RuntimeError("help içinde, komşuya yazdıktan sonra hata")


srv.click_next_state = patlayan
once_ben = kayit(app, ben)
r, body = gateway(c, [("UserService.setWorldName", ["Sağlam ad"]),
                      ("VisitorService.help", [komsu_uid, agaclar[0]["id"], "clear"])])
yaz("patlayan help -> cevaplar:", [(d["errorType"], d.get("errorData")) for d in body["data"]])
yaz("   komşudaki yardım kaydı:", repr(yardimlar()), "(None beklenir) | benim dünya adım:",
    repr(kayit(app, ben)["user_object"]["userInfo"]["worldName"]))
yaz("   oyuncunun görevleri değişmedi mi (tending ilerlemesi geri alındı):",
    kayit(app, ben)["quests"] == once_ben["quests"])
srv.click_next_state = asil
r, body = gateway(c, [("VisitorService.help", [komsu_uid, agaclar[1]["id"], "clear"])])
yaz("sağlam help   -> cevap:", [(d["errorType"], d.get("errorData")) for d in body["data"]],
    "| komşudaki yardım kaydı:", repr(yardimlar()))

# 2) maliyet
c2 = app.test_client()
c2.set_cookie("session", komsu)
gateway(c2, [("UserService.initUser", ["", 0])])
buyuk = kayit(app, komsu)
t = time.perf_counter()
for _ in range(10):
    s = pickle.dumps(dict(buyuk), pickle.HIGHEST_PROTOCOL)
anlik = (time.perf_counter() - t) / 10
yaz("seviye 85 kayıt: pickle anlık görüntü %.1f ms (%d KB)" % (1000 * anlik, len(s) // 1024))
for n in (1, 10, 30):
    ts = []
    for j in range(3):
        t = time.perf_counter()
        gateway(c2, [("UserService.setSeenFlag", ["f%d_%d" % (j, i)]) for i in range(n)])
        ts.append(time.perf_counter() - t)
    yaz("%2d çağrılık paket: ort %.0f ms (çağrı başına anlık görüntü payı ~%.0f ms)" % (
        n, 1000 * sum(ts) / len(ts), 1000 * n * anlik))
