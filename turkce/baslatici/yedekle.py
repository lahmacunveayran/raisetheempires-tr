"""Takes a consistent copy of mygames/save.db (and backups.db) into yedek/ and keeps the newest KEEP copies.

Uses SQLite's online backup API, so it is safe even while the game server is running.
"""
import datetime
import glob
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
KEEP = 10


def backup(name):
    source = os.path.join(HERE, "mygames", name + ".db")
    if not os.path.exists(source):
        return
    target = os.path.join(HERE, "yedek", "%s_%s.db" % (name, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    with sqlite3.connect(target) as check:
        if check.execute("pragma integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Yedek dogrulanamadi: " + target)
    for old in sorted(glob.glob(os.path.join(HERE, "yedek", name + "_*.db")))[:-KEEP]:
        os.remove(old)
    print("Yedek alindi:", os.path.relpath(target, HERE))


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "yedek"), exist_ok=True)
    backup("save")
    backup("backups")
