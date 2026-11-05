"""Yeniden denetim: kayıt başına istek kilidi (AssetSkippingSessionInterface + teardown_request).

1) Gerçek iki iş parçacığı: A (yavaş bir sayfa isteği) kaydı açar, B (oyun paketi) dünya adını değiştirir.
   Kilitle B, A bitene kadar bekler ve B'nin değişikliği kalır. Kilit devre dışıyken (her isteğe yeni kilit) eski
   kayıp-güncelleme geri gelir: kilidin işe yaradığının karşı kanıtı.
2) Hata yollarında kilit bırakılıyor mu: Host 403, 404, görünüm hatası (500), iç open_session hatası,
   save_session hatası (kodlanamayan değer). Her birinden sonra aynı kayıtla yeni bir istek 5 sn içinde bitmeli.
Çalıştırma (bu klasörden): PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y01_kilit.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cekirdek"))
from ortam import kur, gateway, kayit, sessiz, _DEVNULL


def out(*a):
    sys.__stdout__.write(" ".join(str(x) for x in a) + "\n")
    sys.__stdout__.flush()


srv, app, tmp = kur(savespack=False)
sys.stdout = _DEVNULL  # iş parçacıkları da sessiz olsun
c = app.test_client()
gateway(c, [("UserService.initUser", ["", 0])])
sid = c.get_cookie("session").value
asil_home = app.view_functions["home"]


def yavas_home():
    time.sleep(1.0)  # sayfa isteği kaydı açmış, işini yapıyor
    return asil_home()


app.view_functions["home"] = yavas_home


def deneme(ad):
    ca, cb = app.test_client(), app.test_client()
    ca.set_cookie("session", sid)
    cb.set_cookie("session", sid)
    zaman = {}
    t0 = time.time()

    def a():
        ca.get("/home.html")
        zaman["A"] = time.time() - t0

    def b():
        gateway(cb, [("UserService.setWorldName", [ad])])
        zaman["B"] = time.time() - t0

    ta = threading.Thread(target=a)
    ta.start()
    time.sleep(0.3)
    tb = threading.Thread(target=b)
    tb.start()
    ta.join(20)
    tb.join(20)
    return zaman, kayit(app, sid)["user_object"]["userInfo"]["worldName"]


z, son = deneme("Kilitli ad")
out("KİLİTLE   : A bitti %.2f sn, B bitti %.2f sn | kayıttaki ad: %r" % (z["A"], z["B"], son))


class HerSeferYeniKilit(dict):
    def setdefault(self, key, default=None):
        return threading.Lock()


gercek = app.session_interface.locks
app.session_interface.locks = HerSeferYeniKilit()
z, son = deneme("Kilitsiz ad")
out("KİLİTSİZ  : A bitti %.2f sn, B bitti %.2f sn | kayıttaki ad: %r  (B'nin adı ezildi mi: %s)"
    % (z["A"], z["B"], son, son != "Kilitsiz ad"))
app.session_interface.locks = gercek
app.view_functions["home"] = asil_home


def sonraki_istek_bitiyor_mu():
    cc = app.test_client()
    cc.set_cookie("session", sid)
    sonuc = {}
    t = threading.Thread(target=lambda: sonuc.setdefault("r", cc.get("/home.html").status_code))
    t.start()
    t.join(5)
    return "bitti (%s)" % sonuc.get("r") if not t.is_alive() else "KİLİTLİ KALDI"


def dene(baslik, istek):
    try:
        kod = istek()
    except Exception as e:
        kod = "istisna %s" % type(e).__name__
    out("%-42s -> %-28s | ardından aynı kayıtla istek: %s" % (baslik, kod, sonraki_istek_bitiyor_mu()))


cx = app.test_client()
cx.set_cookie("session", sid)
dene("Host: kotu.example (403)", lambda: cx.get("/home.html", headers={"Host": "kotu.example:5005"}).status_code)
dene("olmayan yol (404)", lambda: cx.get("/olmayan-yol").status_code)


def patlayan():
    raise RuntimeError("görünüm hatası")


uc = next(r.endpoint for r in app.url_map.iter_rules() if r.rule == "/friends.html")
app.view_functions[uc] = patlayan
yol = "/friends.html"
dene("görünüm hatası (500) " + yol, lambda: (cx.get(yol).status_code, cx.get(yol).data[:13]))

ic = app.session_interface.inner
asil_open = ic.open_session
sayac = {"n": 0}


def bir_kez_patlayan_open(a, r):
    if sayac["n"] == 0:
        sayac["n"] += 1
        raise RuntimeError("save.db okunamadı")
    return asil_open(a, r)


ic.open_session = bir_kez_patlayan_open
dene("iç open_session hatası", lambda: cx.get("/home.html").status_code)
ic.open_session = asil_open

asil_seen = srv.seen_flag_response


def kodlanamayan_deger(param):
    srv.session["kodlanamaz"] = {1, 2}  # msgspec set'i kodlar mı? -> deneme için object()
    srv.session["kodlanamaz2"] = object()
    return asil_seen(param)


srv.seen_flag_response = kodlanamayan_deger
r, body = gateway(cx, [("UserService.setWorldName", ["Kaybolacak ad"]), ("UserService.setSeenFlag", ["x"])])
out("save_session hatası (object() oturumda)       -> HTTP %s %s | %s" % (r.status_code, r.content_type,
    body if isinstance(body, str) else "AMF"))
out("   kayıttaki ad (sağlam setWorldName kaldı mı?): %r" % kayit(app, sid)["user_object"]["userInfo"]["worldName"])
out("   ardından aynı kayıtla istek:", sonraki_istek_bitiyor_mu())
srv.seen_flag_response = asil_seen
out("kilit sözlüğündeki anahtar sayısı:", len(app.session_interface.locks))
