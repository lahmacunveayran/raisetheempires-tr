"""CEK-10 ve form boyutu kanıtı: savespack/save.db kayıtlarının biçimi (pickle/msgpack), boyutları ve kayıt
düzenleyici formunun URL-kodlanmış boyutu. Dosyanın bir kopyası üzerinde, salt okunur çalışır."""
import sqlite3, sys, json, pickle, msgspec, urllib.parse, shutil, tempfile, os, zlib
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'savespack', 'save.db')
tmp = os.path.join(tempfile.mkdtemp(), "save.db"); shutil.copy(src, tmp)
con = sqlite3.connect(tmp)
print(con.execute("select name, sql from sqlite_master").fetchall())
for sid, data in con.execute("select session_id, data from sessions"):
    data = bytes(data)
    kind = "?"
    try: d = msgspec.msgpack.decode(data); kind = "msgpack"
    except Exception:
        try: d = pickle.loads(data); kind = "pickle"
        except Exception as e: d = None; kind = "bad " + repr(e)
    if not isinstance(d, dict): print(sid, kind, type(d)); continue
    uo = d.get("user_object")
    js = json.dumps({k: d.get(k) for k in ['user_object','profilePic','quests','battle','last_battle','fleets','population','saved','save_version','original_save_version']}, default=lambda o: '<not serializable>', indent=2)
    enc = urllib.parse.urlencode({"savegame": js, "message": ""})
    lvl = uo["userInfo"]["player"]["level"] if uo else None
    print(sid[:20], kind, "raw", len(data), "keys", sorted(k for k in d if k not in ('user_object',)), "lvl", lvl, "objs", len(uo["userInfo"]["world"]["objects"]) if uo else None, "json", len(js), "urlenc", len(enc), "saved_on" in d, d.get("save_version"))
