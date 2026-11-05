"""Denetim ortamı: sunucuyu gerçek oturum katmanıyla (flask-session + SQLAlchemy + msgspec) geçici bir klasörde kurar.

Depoya ve oyuncunun kurulumuna hiçbir şey yazmaz: MyGamesPath geçici klasördür (save.db, backups.db, log.txt orada
oluşur), InstallPath depo köküdür (assets, mods, templates oradan okunur). save.db olarak depodaki
`savespack/save.db` dosyasının bir kopyası kullanılır.

Kullanım (betiklerden):  from ortam import kur;  srv, app, tmp = kur()
"""
import os
import shutil
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def kur(savespack=True):
    tmp = tempfile.mkdtemp(prefix="cekirdek_")
    mg = os.path.join(tmp, "mygames")
    os.makedirs(mg)
    for f in ("gamesettings-converted.json", "questsettings-converted.json"):
        shutil.copy(os.path.join(REPO, f), mg)
    shutil.copytree(os.path.join(REPO, "allies"), os.path.join(mg, "allies"))
    if savespack:
        shutil.copy(os.path.join(REPO, "savespack", "save.db"), os.path.join(mg, "save.db"))
    with open(os.path.join(tmp, "RaiseTheEmpires.ini"), "w") as f:
        f.write("[InstallFolders]\nInstallPath=%s\nMyGamesPath=%s\n" % (REPO, mg))
    os.chdir(tmp)
    sys.path.insert(0, REPO)
    sys.argv = [os.path.join(tmp, "denetim.py")]  # tendo kilidi depodaki/oyuncudaki sunucuyla çakışmasın
    with sessiz():
        srv = __import__("empires-server")
    srv.settings.crash_log = False  # hata olunca Not Defteri açılmasın
    srv.set_crash_log(False)
    sys.excepthook = sys.__excepthook__  # sunucu kendi kancasını kurar; betik hataları görünsün
    app = srv.app
    app.config["TESTING"] = False
    # empires-server.py __main__ bloğundaki kurulumun aynısı (compress ve tarayıcı açma hariç)
    srv.db.init_app(app)
    srv.sess.init_app(app)
    srv.socketio.init_app(app)  # istemci günlüğü (report_*_log) için
    app.session_interface = srv.AssetSkippingSessionInterface(app.session_interface)
    return srv, app, tmp


_DEVNULL = open(os.devnull, "w", encoding="utf-8")  # açık kalır: daiquiri günlüğü içe aktarımda buna bağlanır


class sessiz:
    """Sunucunun print gürültüsünü bastırır; sonuçlar `yaz` ile gerçek çıktıya yazılır."""
    def __enter__(self):
        self.eski = sys.stdout
        sys.stdout = _DEVNULL
    def __exit__(self, *a):
        sys.stdout = self.eski


def yaz(*a):
    print(*a, flush=True)


def amf_batch(calls, endpoint="/1"):
    """calls: [(functionName, params), ...] -> istemcinin gönderdiği gibi AMF3 dispatchBatch gövdesi."""
    from pyamf import remoting
    envelope = remoting.Envelope(3)
    body = [{"flashRevision": None},
            [{"transaction": None, "sequence": i + 1, "stamp": 0, "params": params, "functionName": fn}
             for i, (fn, params) in enumerate(calls)], 0]
    envelope.bodies = [(endpoint, remoting.Request("BaseService.dispatchBatch", body=body, envelope=envelope))]
    return remoting.encode(envelope).getvalue()


GATEWAY = "/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php"


def gateway(client, calls):
    from pyamf import remoting
    with sessiz():
        r = client.post(GATEWAY, data=amf_batch(calls), content_type="application/x-amf")
    try:
        body = remoting.decode(r.data).bodies[0][1].body
    except Exception as e:  # AMF değil
        body = "AMF DEĞİL (%s): %r" % (type(e).__name__, r.data[:60])
    return r, body


def kayit(app, sid):
    """save.db'deki kaydı (oturumu) çözerek döndürür."""
    with app.app_context():
        si = app.session_interface
        rec = si.sql_session_model.query.filter_by(session_id="session:" + sid).first()
        return None if rec is None else si.serializer.decode(bytes(rec.data))


def oturumlar(app):
    with app.app_context():
        si = app.session_interface
        return [r.session_id for r in si.sql_session_model.query.all()]


def hatalar(tmp):
    """Geçici log.txt'deki istisnaların son satırları (dosya:satır + hata), sırayla."""
    path = os.path.join(tmp, "mygames", "log.txt")
    if not os.path.exists(path):
        return []
    out, son_yer = [], None
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.strip()
        if s.startswith('File "') and ("raisetheempires-pr" in s or "cekirdek_" in s):
            son_yer = s.split("\\")[-1]
        elif s and not s.startswith(("File", "^", "~")) and ("Error" in s.split(":")[0] or "Exception" in s.split(":")[0]) \
                and not s.startswith(("Traceback", "20")):
            out.append("%s  <- %s" % (s, son_yer))
            son_yer = None
    return out
