"""Runs the built exe in two layouts and reports where save.db and backups.db end up.
A: installed (MyGamesPath elsewhere); B: portable exe with MyGamesPath=. and a save.db + old backups.db next to it."""
import os, shutil, sqlite3, subprocess, sys, time, urllib.request
from contextlib import closing

here = os.path.dirname(os.path.abspath(__file__))
exe = os.path.join(here, "exe", "dist", "empires-server.exe")
root = os.path.join(here, "exe", "run")
shutil.rmtree(root, ignore_errors=True)


def ini(app_dir, my_games):
    with open(os.path.join(app_dir, "RaiseTheEmpires.ini"), "w") as f:
        f.write("[Info]\nName=RaiseTheEmpires\n[InstallFolders]\nInstallPath=%s\nMyGamesPath=%s\n" % (app_dir, my_games))


def legacy_backups(path):
    with closing(sqlite3.connect(path)) as con, con:
        con.execute("CREATE TABLE backups (id INTEGER PRIMARY KEY AUTOINCREMENT, save_id TEXT NOT NULL, saved_on REAL, "
                    "replaced_on REAL, save_version TEXT, message TEXT, data BLOB NOT NULL)")


def run(app_dir, port):
    log = open(os.path.join(app_dir, "stdout.txt"), "w")
    p = subprocess.Popen([os.path.join(app_dir, "empires-server.exe"), "--no-popup", "--no-crash-log", "--port", str(port)],
                         cwd=app_dir, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/save-editor" % port, timeout=5)
            except urllib.error.HTTPError as e:
                print("  GET /save-editor ->", e.code)
                break
            except Exception:
                time.sleep(1)
                continue
            print("  GET /save-editor -> 200")
            break
        time.sleep(1)
    finally:
        p.kill()
        p.wait()
        log.close()
    out = open(os.path.join(app_dir, "stdout.txt"), encoding="utf-8", errors="replace").read().splitlines()
    for l in out:
        if any(k in l for k in ("Root folder", "Instance folder", "SQLITE", "backups.db", "save.db", "Traceback")):
            print("  |", l)


def files(base):
    for d, _, fs in os.walk(base):
        for f in fs:
            if f.endswith(".db"):
                print("  ", os.path.relpath(os.path.join(d, f), root))


# A: installed
a_app, a_games = os.path.join(root, "A", "app"), os.path.join(root, "A", "My Games")
os.makedirs(a_app); os.makedirs(a_games)
shutil.copy(exe, a_app); ini(a_app, a_games)
print("A installed:"); run(a_app, 5091); files(os.path.join(root, "A"))

# B: portable, MyGamesPath=. with save.db and an old backups.db next to the exe
b_app = os.path.join(root, "B", "app")
os.makedirs(b_app)
shutil.copy(exe, b_app); ini(b_app, ".")
sqlite3.connect(os.path.join(b_app, "save.db")).close()
legacy_backups(os.path.join(b_app, "backups.db"))
print("B portable (MyGamesPath=.):"); run(b_app, 5092); files(os.path.join(root, "B"))
with closing(sqlite3.connect(os.path.join(b_app, "instance", "backups.db"))) as con:
    print("  columns of instance/backups.db:", [r[1] for r in con.execute("PRAGMA table_info(backups)")])
