"""Evidence: a power's <against> modifier never applies to a Titan part (server), the client applies it."""
import contextlib, copy, io, json, os, sys
ROOT = r"C:\Users\<user>\Desktop\Raise\raisetheempires-pr"
sys.path.insert(0, ROOT); os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    from flask import Flask, session
    import battle_engine
battle_engine.report_battle_log = lambda *a: None
app = Flask(__name__); app.secret_key = "x"
user = json.load(open(os.path.join(ROOT, "test", "init_user.json")))
with app.test_request_context():
    session["user_object"] = copy.deepcopy(user); session["quests"] = []; session["battle"] = None
    n04 = battle_engine.lookup_item_by_code("N04")
    for code, full in (("U05", 100), ("ML11", 1200)):
        unit = battle_engine.lookup_item_by_code(code)
        left = [full]
        with contextlib.redirect_stdout(io.StringIO()):
            battle_engine.apply_consumable_direct_impact({}, n04, 0, [unit], left, {}, False, [])
        print(code, unit["unit"]["-type"], "type/terrain used:", battle_engine.get_unit_type(unit),
              battle_engine.get_unit_terrain(unit), "N04 damage:", full - left[0])
