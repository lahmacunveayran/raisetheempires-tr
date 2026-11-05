import copy, json, sys, os, tempfile
sys.argv = ["probe2_kayit"]
import save_engine
save_engine.set_crash_log(False)
tmp = tempfile.mkdtemp()
save_engine.backup_db_path = lambda: os.path.join(tmp, "backups.db")
es = __import__("empires-server")
import save_migration, quest_engine
INIT = json.load(open("test/init_user.json"))
from flask import Flask
app = Flask("p"); app.secret_key = "t"
with app.test_request_context():
    es.session["user_object"] = copy.deepcopy(INIT)
    es.session["quests"] = [{"name": "Q0516", "complete": False, "expired": False, "progress": [1], "completedTasks": 1},
                            {"name": "Q0531", "complete": False, "expired": False, "progress": [0], "completedTasks": 1}]
    es.session["save_version"] = "0.02a"
    print(quest_engine.lookup_quest("Q0516")["tasks"])
    meta = {}
    save_migration.migrate(meta, "0.02a", "0.03a")
    print(es.session["quests"])
    print(meta)
    print(es.session["user_object"]["userInfo"]["player"]["expansions"])
    print(sorted(es.session["user_object"]["experiments"].items()))
