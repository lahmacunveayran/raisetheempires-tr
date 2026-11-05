"""Yeniden denetim: başka bir kayda yazım (store_session -> write_session) o kaydın kilidini almıyor.

B, komşu kaydı Y'yi açmış bir istektir (ör. ikinci bir tarayıcıda Y ile oynanıyor ya da Y'nin sayfası açılıyor).
Bu sırada A (kendi kaydıyla) Y'ye VisitorService.help yapar; write_session Y'yi hemen yazar. B bitince Y'yi
okuduğu eski hâliyle geri yazar: A'nın yardımı Y'den kaybolur (A'nın kendi kaydında görev ilerlemesi kalır).
Çalıştırma: PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y06_baska_kayit_kilidi.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cekirdek"))
from ortam import kur, gateway, kayit, oturumlar, _DEVNULL


def out(*a):
    sys.__stdout__.write(" ".join(str(x) for x in a) + "\n")
    sys.__stdout__.flush()


srv, app, tmp = kur()
sys.stdout = _DEVNULL
ids = [i[len("session:"):] for i in oturumlar(app)]
ben = next(i for i in ids if i.startswith("c519d7e7"))
komsu = next(i for i in ids if i.startswith("623fecce"))
k = kayit(app, komsu)
komsu_uid = k["user_object"]["userInfo"]["player"]["uid"]
agac = next(o for o in k["user_object"]["userInfo"]["world"]["objects"] if o["itemName"].startswith("tree"))
ca = app.test_client()
ca.set_cookie("session", ben)
gateway(ca, [("UserService.initUser", ["", 0])])
benim_uid = str(kayit(app, ben)["user_object"]["userInfo"]["player"]["uid"])

asil = app.view_functions["home"]
app.view_functions["home"] = lambda: (time.sleep(1.0), asil())[1]
cb = app.test_client()
cb.set_cookie("session", komsu)
tb = threading.Thread(target=lambda: cb.get("/home.html"))
tb.start()
time.sleep(0.3)
r, body = gateway(ca, [("VisitorService.help", [komsu_uid, agac["id"], "clear"])])
hemen = (kayit(app, komsu)["user_object"].get("visitorHelpRequests") or {}).get(benim_uid)
tb.join(10)
sonra = (kayit(app, komsu)["user_object"].get("visitorHelpRequests") or {}).get(benim_uid)
out("help cevabı:", [d["errorType"] for d in body["data"]], "| Y'de yardım, help'ten hemen sonra: %r" % hemen,
    "| Y'nin açık isteği bitince: %r" % sonra)
