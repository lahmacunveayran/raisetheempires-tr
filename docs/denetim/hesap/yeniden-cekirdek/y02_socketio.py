"""Yeniden denetim: Socket.IO ile kayıt kilidi ve Host denetimi.

1) Flask-SocketIO her olayı app.request_context(environ) içinde çalıştırır; bu, oturumu (ve artık kayıt kilidini)
   açar. Bir oyun paketi kilidi tutarken gelen olay bekler mi, sonra kilit bırakılıyor mu?
2) /socket.io/ istekleri Flask'tan önce engineio ara katmanında karşılanır; reject_unknown_hosts burada çalışmaz.
   Yabancı bir alan adıyla (DNS rebinding: Host ve Origin aynı yabancı ad) el sıkışma kabul ediliyor mu?
Çalıştırma: PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y02_socketio.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cekirdek"))
from ortam import kur, gateway, _DEVNULL


def out(*a):
    sys.__stdout__.write(" ".join(str(x) for x in a) + "\n")
    sys.__stdout__.flush()


srv, app, tmp = kur(savespack=False)
sys.stdout = _DEVNULL
c = app.test_client()
gateway(c, [("UserService.initUser", ["", 0])])
sid = c.get_cookie("session").value

# 1) olay, kilidi tutan paketin bitmesini bekliyor mu
sio = srv.socketio.test_client(app, flask_test_client=c)
out("socket.io test istemcisi bağlandı:", sio.is_connected())
asil = srv.seen_flag_response
basladi, devam = threading.Event(), threading.Event()


def yavas(param):
    basladi.set()
    devam.wait(10)
    return asil(param)


srv.seen_flag_response = yavas
cb = app.test_client()
cb.set_cookie("session", sid)
t = threading.Thread(target=lambda: gateway(cb, [("UserService.setSeenFlag", ["x"])]))
t.start()
basladi.wait(10)
olay_bitti = threading.Event()
te = threading.Thread(target=lambda: (sio.emit("message", "merhaba"), olay_bitti.set()))
te.start()
out("paket kilidi tutarken 'message' olayı 0,5 sn içinde bitti mi:", olay_bitti.wait(0.5))
devam.set()
t.join(10)
out("paket bitince olay bitti mi:", olay_bitti.wait(5))
srv.seen_flag_response = asil
cc = app.test_client()
cc.set_cookie("session", sid)
t0 = time.time()
th = threading.Thread(target=lambda: cc.get("/home.html"))
th.start()
th.join(5)
out("olaydan sonra aynı kayıtla sayfa isteği bitti mi:", not th.is_alive(), "(%.2f sn)" % (time.time() - t0))

# 2) Host denetimi socket.io'da
yabanci = app.test_client()
for host, origin in (("kotu.example:5005", "http://kotu.example:5005"), ("127.0.0.1:5005", "http://127.0.0.1:5005")):
    r = yabanci.get("/socket.io/?EIO=4&transport=polling", headers={"Host": host, "Origin": origin})
    out("socket.io el sıkışma Host=%-18s -> HTTP %s %r" % (host, r.status_code, r.data[:40]))
r = yabanci.get("/home.html", headers={"Host": "kotu.example:5005"})
out("karşılaştırma: /home.html Host=kotu.example       -> HTTP", r.status_code)
