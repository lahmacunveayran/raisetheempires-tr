"""CEK: her oyun isteğinin sabit maliyeti (büyük kayıtta): kayıt okuma + pickle anlık görüntü + msgspec yazma.
savespack'teki en büyük kayıt (seviye 85, 1288 nesne) ile basit bir çağrı (setSeenFlag) 10 kez."""
import sys, os, time, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz, sessiz

srv, app, tmp = kur()
sid = next(i for i in oturumlar(app) if i.startswith("session:623fecce"))[len("session:"):]
c = app.test_client()
c.set_cookie("session", sid)
t = time.perf_counter(); gateway(c, [("UserService.initUser", ["", 0])]); yaz("initUser: %.2f s" % (time.perf_counter() - t))
k = kayit(app, sid)
with app.app_context():
    rec = app.session_interface.sql_session_model.query.filter_by(session_id="session:" + sid).first()
    yaz("kayıt boyutu (msgpack): %.0f KB | pickle: %.0f KB" % (len(bytes(rec.data)) / 1024, len(pickle.dumps(k, 5)) / 1024))
ts = []
for i in range(10):
    t = time.perf_counter(); gateway(c, [("UserService.setSeenFlag", ["f%d" % i])]); ts.append(time.perf_counter() - t)
yaz("setSeenFlag x10: ort %.0f ms, en çok %.0f ms" % (1000 * sum(ts) / len(ts), 1000 * max(ts)))
with app.test_request_context():
    import flask
    flask.session.sid = sid
    flask.session.update(k)
    t = time.perf_counter()
    with sessiz():
        for i in range(5):
            srv.create_backup("ölçüm")
    yaz("create_backup (seviye atlama başına bir kez): ort %.0f ms" % (1000 * (time.perf_counter() - t) / 5))
t = time.perf_counter()
with app.test_request_context():
    with sessiz():
        n = len(srv.get_saves())
yaz("get_saves() (%d kayıt, initUser/loadWorld/home.html her seferinde): %.0f ms" % (n, 1000 * (time.perf_counter() - t)))
