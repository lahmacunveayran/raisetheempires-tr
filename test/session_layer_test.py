"""Tests through the server's real save game layer: flask-session with SQLAlchemy and msgspec, the way
empires-server.py sets it up when it runs (configure_app, the `server` fixture of conftest.py), with save.db in a
temporary folder."""
import copy
import html
import json
import logging
import logging.handlers
import os
import pickle
import re
import sqlite3
import threading
import types
from datetime import datetime

import pyamf
import pytest
from pyamf import remoting

empires_server = __import__('empires-server')
import game_settings
import logger
import save_engine
import save_migration

# The client posts its batches to app_url + "flashservices/gateway.php": the Flash player's app_url is the folder of
# ZGame.109338.swf (/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1), Ruffle's the absolute /127.0.0.1
GATEWAY = "/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php"
RUFFLE_GATEWAY = "/127.0.0.1flashservices/gateway.php"
VALID_USER_OBJECT = {"userInfo": {"worldName": "Test", "world": {"resources": {"coins": 10}}, "player": {
    "level": 5, "uid": 1, "xp": 0, "playerResourceType": 0, "socialXpGood": 0, "socialLevelGood": 1,
    "socialXpBad": 0, "socialLevelBad": 1}}}
with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)


@pytest.fixture(params=[GATEWAY, RUFFLE_GATEWAY], ids=["flash", "ruffle"])
def gateway(request):
    return request.param


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(logger.socketio, "emit", lambda *args, **kwargs: None)  # no log page in tests
    monkeypatch.setattr(empires_server.settings, "crash_log", False)


def new_save(app, **values):
    """A client with a save game of its own, and that save's id."""
    client = app.test_client()
    with client.session_transaction() as save:
        save.update(values)
    return client, client.get_cookie("session").value


def stored(app, sid):
    with app.app_context():
        interface = app.session_interface
        record = interface.sql_session_model.query.filter_by(session_id="session:" + sid).first()
        return None if record is None else interface.serializer.decode(bytes(record.data))


def raw_record(app, sid):
    with app.app_context():
        record = app.session_interface.sql_session_model.query.filter_by(session_id="session:" + sid).first()
        return bytes(record.data)


def batch(client, *calls, gateway=GATEWAY):
    """Sends calls [(functionName, params), ...] like the client does, returns the answers to the calls."""
    envelope = remoting.Envelope(3)
    body = [{"flashRevision": None}, [{"transaction": None, "sequence": i + 1, "stamp": 0, "params": params,
                                       "functionName": name} for i, (name, params) in enumerate(calls)], 0]
    envelope.bodies = [("/1", remoting.Request("BaseService.dispatchBatch", body=body, envelope=envelope))]
    response = client.post(gateway, data=remoting.encode(envelope).getvalue(), content_type="application/x-amf")
    assert response.content_type == "application/x-amf"
    return remoting.decode(response.data).bodies[0][1].body["data"]


def fleet(name):
    return {"name": name, "units": ["U01,10,0,0,0"]}


def test_a_failing_call_is_undone_and_the_other_calls_are_kept(server, monkeypatch, gateway):
    other_client, other_sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    client, sid = new_save(server, fleets={})
    add_fleet = empires_server.add_fleet_response

    def add_fleet_or_fail(param):
        if param["name"] == "bad":
            empires_server.session["fleets"]["half_done"] = []
            other = dict(stored(server, other_sid), session_id="session:" + other_sid, changed_by_failed_call=True)
            empires_server.store_session(other)
            raise RuntimeError("call fails")
        return add_fleet(param)

    monkeypatch.setattr(empires_server, "add_fleet_response", add_fleet_or_fail)
    answers = batch(client, ("WorldService.addFleet", [fleet("first")]), ("WorldService.addFleet", [fleet("bad")]),
                    ("WorldService.addFleet", [fleet("last")]), gateway=gateway)

    assert [answer["errorType"] for answer in answers] == [0, empires_server.CALL_FAILED, 0]
    assert answers[1]["errorData"] == "WorldService.addFleet"
    # the failed call's answer has the fields of every answer (those of the calls that worked) and errorData, no data
    assert set(answers[1]) == set(answers[0]) | {"errorData"} and answers[1]["data"] is None
    assert set(stored(server, sid)["fleets"]) == {"first", "last"}
    assert "changed_by_failed_call" not in stored(server, other_sid)


class WatchedLock:
    """A save lock that tells when a request has to wait for it: it is asked for while another request has it."""
    def __init__(self):
        self.lock = threading.Lock()
        self.waited_for = threading.Event()

    def acquire(self, *args, **kwargs):
        if self.lock.locked():
            self.waited_for.set()
        return self.lock.acquire(*args, **kwargs)

    def release(self):
        self.lock.release()


def test_overlapping_requests_of_one_save_wait_for_each_other(server, monkeypatch, gateway):
    client, sid = new_save(server, fleets={})
    other_client = server.test_client()
    other_client.set_cookie("session", sid)
    lock = server.session_interface.locks[sid] = WatchedLock()  # the lock of this save (by its cookie), watched
    slow_started, go_on = threading.Event(), threading.Event()
    calls = []
    add_fleet = empires_server.add_fleet_response

    def slow_add_fleet(param):
        calls.append(param["name"] + " starts")
        if param["name"] == "slow":
            slow_started.set()
            go_on.wait(10)
        answer = add_fleet(param)
        calls.append(param["name"] + " ends")
        return answer

    monkeypatch.setattr(empires_server, "add_fleet_response", slow_add_fleet)
    slow = threading.Thread(target=batch, args=(client, ("WorldService.addFleet", [fleet("slow")])),
                            kwargs={"gateway": gateway})
    fast = threading.Thread(target=batch, args=(other_client, ("WorldService.addFleet", [fleet("fast")])),
                            kwargs={"gateway": gateway})
    slow.start()
    try:
        assert slow_started.wait(10)
        fast.start()
        # the fast request asks for the save while the slow one has it (the 10 s only end a broken run)
        assert lock.waited_for.wait(10)
        assert calls == ["slow starts"]  # and its call has not started
    finally:  # no request may outlive the test, also when it fails
        go_on.set()
        slow.join(10)
        if fast.ident is not None:  # started
            fast.join(10)

    assert calls == ["slow starts", "slow ends", "fast starts", "fast ends"]
    assert set(stored(server, sid)["fleets"]) == {"slow", "fast"}  # without waiting, slow writes over fast's fleet


def test_answers_only_ip_addresses_and_localhost(server):
    client = server.test_client()
    for host in ("127.0.0.1:5005", "localhost:5005", "192.168.1.20:5005", "[::1]:5005", "localhost"):
        assert client.get("/127.0.0.1record_stats.php", headers={"Host": host}).status_code == 204, host
    for host in ("evil.example:5005", "evil.example", "127.0.0.1.evil.example", "evil-localhost.example",
                 "localhost.evil.example:5005"):
        assert client.get("/127.0.0.1record_stats.php", headers={"Host": host}).status_code == 403, host


def test_host_names_that_only_contain_localhost_are_unknown():
    """is_known_host: "Only an IP address or localhost" (its docstring), a name with localhost in it is neither."""
    for host in ("evil-localhost.example", "localhost.evil.example", "evil-localhost.example:5005",
                 "localhost.evil.example:5005", "mylocalhost", "localhost.:5005"):
        assert not empires_server.is_known_host(host), host
    for host in ("localhost", "LocalHost:5005", "127.0.0.1", "[::1]:5005", "192.168.1.20"):
        assert empires_server.is_known_host(host), host


def test_deleting_a_save_keeps_a_backup(server, backup_db, tmp_path):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    assert client.get("/wipe_session").status_code == 302

    with sqlite3.connect(tmp_path / "backups.db") as con:
        rows = con.execute("SELECT save_id, message FROM backups").fetchall()
    assert rows == [(sid, "Before deleting the save game")]


def test_an_invalid_save_still_answers_every_call(server):
    client, _ = new_save(server, user_object={"userInfo": {}}, quests=[])
    answers = batch(client, ("UserService.initUser", ["", 0]), ("UserService.publishUserAction", [{}]))

    assert [answer["errorType"] for answer in answers] == [empires_server.CALL_FAILED, 0]


def test_values_the_client_left_undefined_can_be_saved(server):
    serializer = server.session_interface.serializer
    assert serializer.decode(serializer.encode({"a": pyamf.Undefined, "b": [1, pyamf.Undefined]})) == \
        {"a": None, "b": [1, None]}
    assert empires_server.dense_arrays(pyamf.Undefined) is None


def test_other_saves_are_written_as_msgpack(server):
    _, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    with server.test_request_context():
        save_engine.store_session(dict(stored(server, sid), session_id="session:" + sid, visited=True))

    assert not raw_record(server, sid).startswith(b"\x80")
    assert stored(server, sid)["visited"]


def test_pickled_saves_are_converted_once(server):
    save = {"user_object": VALID_USER_OBJECT, "quests": [], "fleets": {"fleet1": ["U01,10,0,0,0"]}}
    with server.app_context():
        interface = server.session_interface
        interface.client.session.add(interface.sql_session_model("session:pickled", pickle.dumps(save), None))
        interface.client.session.commit()
        save_engine.convert_pickled_saves()

        converted = raw_record(server, "pickled")
        save_engine.convert_pickled_saves()  # on the next start: a msgpack save is left as it is

    assert not converted.startswith(b"\x80")
    assert raw_record(server, "pickled") == converted
    assert stored(server, "pickled") == save


def test_save_editor_writes_nothing_of_an_incomplete_save(server, backup_db):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[], battle=None, fleets={},
                           population=None)
    edited = dict(user_object=json.loads(json.dumps(VALID_USER_OBJECT)), battle=None, fleets={}, population=None)
    edited["user_object"]["userInfo"]["worldName"] = "Edited"

    assert client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "x"}).status_code == 400
    assert stored(server, sid)["user_object"]["userInfo"]["worldName"] == "Test"

    edited["quests"] = []
    assert client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "x"}).status_code == 302
    assert stored(server, sid)["user_object"]["userInfo"]["worldName"] == "Edited"


def save_editor_page(client):
    """The save game the save editor shows, or None for any other page (the error page is 'It went wrong')."""
    page = client.get("/save-editor").get_data(as_text=True)
    textarea = re.search(r'<textarea rows="30" cols="135" name="savegame" >(.*?)</textarea>', page, re.S)
    return json.loads(html.unescape(textarea.group(1))) if textarea else None


SAVE_EDITOR_KEYS = ("user_object", "profilePic", "quests", "battle", "last_battle", "fleets", "population", "saved",
                    "save_version", "original_save_version")


def test_save_editor_opens_for_a_new_save(server):
    # save_editor: every key the save does not have is shown as null, a new save has none of them (no quests either)
    assert save_editor_page(server.test_client()) == dict.fromkeys(SAVE_EDITOR_KEYS)


def test_save_editor_lists_the_quests_of_a_save(server):
    client, _ = new_save(server, user_object=VALID_USER_OBJECT, quests=[{"name": "Q0516", "complete": False}])
    shown = save_editor_page(client)
    assert shown["quests"] == [{"name": "Q0516", "complete": False}]
    assert shown["user_object"] == VALID_USER_OBJECT


def test_old_backups_without_dates_are_listed_from_1970():
    """format_backup_message: saved_on - replaced_on @version message, no date counts as 0 (the start of 1970 in the
    local time zone), no version as UNKNOWN VERSION."""
    def local(timestamp):
        return datetime.fromtimestamp(timestamp).strftime("%d %b %Y %H:%M:%S")
    assert empires_server.format_backup_message({"saved_on": None, "replaced_on": None}) == \
        local(0) + " - " + local(0) + " @UNKNOWN VERSION "
    assert empires_server.format_backup_message({"saved_on": 86400, "replaced_on": 90000, "save_version": "0.08a",
                                                 "message": "Level 5"}) == \
        local(86400) + " - " + local(90000) + " @0.08a Level 5"


def test_save_editor_writes_nothing_of_an_invalid_user_object(server):
    """save_savegame checks everything before writing anything (its comment): quests are fine, but a user_object
    without a player is not a save game."""
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    edited = {"user_object": {"userInfo": {"worldName": "Edited"}}, "quests": []}
    response = client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "x"})

    assert response.status_code == 400 and response.get_data(as_text=True).startswith("Not saved")
    assert stored(server, sid)["user_object"] == VALID_USER_OBJECT


def test_save_editor_takes_an_old_backup_without_battle_fleets_and_population(server):
    """save_savegame: "an older backup may not have these" (battle, fleets, population): they are emptied."""
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[], battle=None, fleets={"fleet1_1": []},
                           population=5, save_version="0.08a")
    old = {"user_object": copy.deepcopy(VALID_USER_OBJECT), "quests": []}
    old["user_object"]["userInfo"]["worldName"] = "Old"
    response = client.post("/save-editor", data={"savegame": json.dumps(old), "message": "x"})

    assert response.status_code == 302 and response.headers["Location"].endswith("/home.html")
    save = stored(server, sid)
    assert save["user_object"]["userInfo"]["worldName"] == "Old"
    assert (save["battle"], save["fleets"], save["population"], save["save_version"]) == (None, None, None, None)


@pytest.mark.parametrize("modded", [b"<settings/>", "<settings/>"])  # a replaced file, an xmldiff
def test_mods_of_the_settings_files_are_served(server, monkeypatch, modded):
    for path, route in (("assets/29oct2012/gameSettings_with_fixes.xml", "/gameSettings.xml"),
                        ("assets/29oct2012/questSettings_with_fixes.xml", "/127.0.0.1questSettings.xml")):
        monkeypatch.setitem(empires_server.mod_engine.mod, path, lambda: modded)
        response = server.test_client().get(route)
        assert response.status_code == 200, route
        assert b"<settings" in response.data, route


def test_the_settings_files_are_served_without_a_mod(server, monkeypatch):
    for path in ("assets/29oct2012/gameSettings_with_fixes.xml", "assets/29oct2012/questSettings_with_fixes.xml"):
        monkeypatch.delitem(empires_server.mod_engine.mod, path, raising=False)
    client = server.test_client()

    # what only the files themselves have: assets/29oct2012/gameSettings_with_fixes.xml starts with
    # <settings><gamesettings and has the combat chain, questSettings_with_fixes.xml starts with <quests><quest
    game = client.get("/gameSettings.xml")
    assert game.mimetype == "text/xml" and b"<settings><gamesettings " in game.data[:200]
    assert b'<chain type="infantry" great="antitank"' in game.data
    quests = client.get("/127.0.0.1questSettings.xml")
    assert b"<quests><quest " in quests.data[:200]


def test_crew_from_another_local_save(server, monkeypatch):
    building = {}
    monkeypatch.setattr(empires_server, "lookup_object", lambda building_id: building)
    monkeypatch.setattr(empires_server, "lookup_crew_template",
                        lambda name: {"-numUnbuyableSlots": "0", "position": [{}, {}, {}]})
    with server.test_request_context():
        empires_server.crew_request_response([[124, 2681928178598866.0, 111], 10003, "Parliament", "crew"])

    # "only neighbor allies can be added": 124 is MissTery (allies/MissTery-island.json, "neighbor": false), 111
    # AcidCaos (a neighbor); 2681928178598866 is not in allies/ (another local save) and its id came as a double
    assert building["crewInfo"] == ["2681928178598866", "111"]


def test_list_of_a_missing_object_can_be_logged(monkeypatch):
    emitted = []
    monkeypatch.setattr(logger.socketio, "emit", lambda *args: emitted.append(args))
    logger.report_world_log("list", [], {}, 1, "/1", None, 0)

    # report_world_log: an empty list is logged as {} with no id, so as "response"; never_fails would hide an
    # error here, then nothing is emitted at all
    assert emitted == [("world_log", ["list", "response", {}, 1, "/1", None, 0, [], []])]


def test_an_answer_of_none_can_be_logged(monkeypatch):
    emitted = []
    monkeypatch.setattr(logger.socketio, "emit", lambda *args: emitted.append(args))
    logger.report_world_log("op", None, {}, 1, "/1", None, 0)

    # report_world_log: only a dict answer is logged by its id, anything else (None) as it is
    assert emitted == [("world_log", ["op", None, {}, 1, "/1", None, 0, [], None])]


def test_logging_for_the_log_page_never_fails_the_call(monkeypatch, capsys):
    def log_page_gone(*args):
        raise RuntimeError("no log page")
    monkeypatch.setattr(logger.socketio, "emit", log_page_gone)

    # never_fails: "Logging for the log page must never fail the call it reports on"
    assert logger.report_world_log("op", {"id": 1}, {}, 1, "/1", None, 0) is None
    assert logger.report_tutorial_step("no such step", None, 0, 1, "/1") is None  # describe_step finds no step
    assert capsys.readouterr().out.count("Could not report to the log page:") == 2


def test_every_state_machine_of_the_items_can_be_looked_up():
    items = [item for item in game_settings.game_settings["settings"]["items"]["item"] if "stateMachineValues" in item]
    failed = []
    for item in items:
        values = item["stateMachineValues"]
        try:
            game_settings.lookup_state_machine(values["-stateMachineName"], values.get("define", []))
        except Exception as error:
            failed.append((item["-name"], repr(error)))

    assert len(items) > 300
    assert failed == []


def test_an_unknown_state_machine_is_an_error():
    with pytest.raises(ValueError, match="No state machine NoSuchStateMachine"):
        game_settings.lookup_raw_state_machine("NoSuchStateMachine")
    with pytest.raises(ValueError, match="No state machine NoSuchStateMachine"):
        game_settings.lookup_state_machine("NoSuchStateMachine", [])


def test_a_stale_battle_answer_is_left_alone_by_the_client(server, monkeypatch):
    def stale(params):
        raise empires_server.StaleBattleReference("battle already over")

    monkeypatch.setattr(empires_server, "battle_complete_response", stale)
    with server.test_request_context():
        answer = empires_server.call_response(types.SimpleNamespace(
            functionName="WorldService.resolveBattle", params=[{}], sequence=1), "/1")

    assert answer["errorType"] == 0 and answer["data"] is None  # onComplete is only called for data that isn't null


def test_migration_remembers_the_version_of_0_08a_saves(server):
    with server.test_request_context():
        empires_server.session["user_object"] = {"experiments": {"empire_mech_lab_master": 3}}
        empires_server.session["save_version"] = "0.08a"
        save_migration.migrate({}, "0.08a", "0.08a.2026_08_13")

        assert empires_server.session["save_version"] == "0.08a.2026_08_13"


def test_a_backup_that_cannot_be_written_does_not_stop_the_migration(server, monkeypatch):
    """save_migration.backup: "a backups.db that can't be written (locked, disk full) must not stop the save game
    from loading"."""
    def locked(message):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(save_migration, "create_backup", locked)
    with server.test_request_context():
        empires_server.session["user_object"] = {"experiments": {}, "userInfo": {"world": {"objects": []}}}
        empires_server.session["save_version"] = "0.06a"
        save_migration.migrate({}, "0.06a", "0.08a.2026_08_13")

        assert empires_server.session["save_version"] == "0.08a.2026_08_13"
        assert empires_server.session["user_object"]["experiments"]["empire_mech_lab_master"] == 3  # 0.08a full


def test_migrating_a_0_02a_save_keeps_a_backup(server, tmp_path):
    """The update to 0.03a resets the quests and expansions, a backup is made before (its comment)."""
    with server.test_request_context():
        empires_server.session["user_object"] = copy.deepcopy(INIT_USER)
        empires_server.session["quests"] = [{"name": "Q0516", "complete": False, "expired": False,
                                              "progress": [1], "completedTasks": 1}]
        empires_server.session["save_version"] = "0.02a"
        save_migration.migrate({}, "0.02a", "0.03a")

        assert empires_server.session["save_version"] == "0.03a"
        assert empires_server.session["quests"][0]["completedTasks"] == 0
    with sqlite3.connect(tmp_path / "backups.db") as con:
        rows = con.execute("SELECT message, save_version FROM backups").fetchall()
    assert rows == [("Update to 0.03a", "0.02a")]  # the save as it was before


def test_init_user_migrates_a_0_08a_preview_save(server, monkeypatch, tmp_path):
    """A 0.08a save without empire_mech_lab_master is from the 0.08a preview: initUser migrates it ("includes from
    preview 0.08a with same version number") and it gets the server's version."""
    monkeypatch.setattr(empires_server, "get_saves", lambda: [])  # no neighbors from the other tests' saves
    monkeypatch.setattr(empires_server.quest_trees, "_spots_file", lambda: str(tmp_path / "quest_tree_spots.json"))
    user_object = copy.deepcopy(INIT_USER)
    del user_object["experiments"]["empire_mech_lab_master"]
    client, sid = new_save(server, user_object=user_object, quests=[], save_version="0.08a")
    answers = batch(client, ("UserService.initUser", ["", 0]))

    assert answers[0]["errorType"] == 0
    save = stored(server, sid)
    assert save["save_version"] == empires_server.version
    assert save["user_object"]["experiments"]["empire_mech_lab_master"] == 3  # set by the 0.08a full step


def test_other_saves_changed_by_a_call_that_works_are_written(server, monkeypatch, gateway):
    """defer_save_writes: other save games written in the block are written when it ends without an error."""
    other_client, other_sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    client, sid = new_save(server, fleets={})
    add_fleet = empires_server.add_fleet_response

    def add_fleet_and_change_the_other_save(param):
        other = dict(stored(server, other_sid), session_id="session:" + other_sid, changed_by_call=True)
        empires_server.store_session(other)
        return add_fleet(param)

    monkeypatch.setattr(empires_server, "add_fleet_response", add_fleet_and_change_the_other_save)
    answers = batch(client, ("WorldService.addFleet", [fleet("first")]), gateway=gateway)

    assert [answer["errorType"] for answer in answers] == [0]
    assert stored(server, other_sid)["changed_by_call"] is True
    assert set(stored(server, sid)["fleets"]) == {"first"}


def test_bytes_the_client_sent_can_be_saved(server):
    """enc_hook: a ByteArray of the client (AMF3) is saved as its bytes."""
    serializer = server.session_interface.serializer
    assert serializer.decode(serializer.encode({"picture": pyamf.amf3.ByteArray(b"ab")})) == {"picture": b"ab"}
    _, sid = new_save(server, picture=pyamf.amf3.ByteArray(b"ab"))
    assert stored(server, sid)["picture"] == b"ab"


def test_world_names_cannot_end_the_home_page_script():
    text = empires_server.script_json([{"name": "</script><b>x</b>"}])

    assert "</" not in text
    assert json.loads(text) == [{"name": "</script><b>x</b>"}]


@pytest.mark.parametrize("page", ["/home.html", "/ruffle.html", "/nodebug.html"])
def test_world_names_cannot_end_the_script_of_the_game_pages(server, page):
    """The friends of getFriendData are the other saves, by their world names: a name with </script> in it must not
    end the page's script, and the friends must still be the JSON the page returns."""
    user_object = copy.deepcopy(VALID_USER_OBJECT)
    user_object["userInfo"]["worldName"] = "</script><b>x</b>"
    client, _ = new_save(server, user_object=user_object, quests=[])
    text = client.get(page).get_data(as_text=True)

    assert "</script><b>" not in text
    friends = re.search(r"function getFriendData\(\) \{.*?return (.*?);\s*\}", text, re.S)
    assert friends, text[:100]  # the error page ('It went wrong') has no script
    assert "</script><b>x</b>" in [friend["name"] for friend in json.loads(friends.group(1))]


def test_every_path_checks_the_host_also_socketio():
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    client = Client(empires_server.KnownHostsOnly(Response("ok")))  # around Flask-SocketIO's middleware in the server

    for host in ("evil.example:5005", "evil-localhost.example:5005", "localhost.evil.example"):
        assert client.get("/socket.io/?EIO=4&transport=polling", headers={"Host": host}).status_code == 403, host
    assert client.get("/socket.io/?EIO=4&transport=polling", headers={"Host": "localhost:5005"}).status_code == 200
    assert client.get("/socket.io/?EIO=4&transport=polling", headers={"Host": "127.0.0.1:5005"}).status_code == 200


def test_a_call_that_leaves_an_unsaveable_value_is_undone(server, monkeypatch, gateway):
    client, sid = new_save(server, fleets={})
    add_fleet = empires_server.add_fleet_response

    def add_unsaveable_fleet(param):
        if param["name"] == "bad":
            empires_server.session["fleets"]["bad"] = object()
        return add_fleet(param) if param["name"] != "bad" else empires_server.dummy_response()

    monkeypatch.setattr(empires_server, "add_fleet_response", add_unsaveable_fleet)
    answers = batch(client, ("WorldService.addFleet", [fleet("bad")]), ("WorldService.addFleet", [fleet("good")]),
                    gateway=gateway)

    assert [answer["errorType"] for answer in answers] == [empires_server.CALL_FAILED, 0]
    assert set(stored(server, sid)["fleets"]) == {"good"}


def test_save_editor_refuses_what_is_not_a_save_game(server):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    for text in ("not json", "[1, 2]"):
        assert client.post("/save-editor", data={"savegame": text, "message": "x"}).status_code == 400, text
    assert stored(server, sid)["user_object"] == VALID_USER_OBJECT


def test_one_crash_log_editor_at_a_time(monkeypatch):
    opened, close = [], threading.Event()
    monkeypatch.setattr(empires_server.settings, "crash_log", True)
    monkeypatch.setattr(empires_server.editor, "edit", lambda **kwargs: (opened.append(kwargs), close.wait(10)))
    monkeypatch.setattr(empires_server, "crash_log_editor", None)
    with empires_server.app.test_request_context():
        empires_server.server_error_page(None)
        empires_server.server_error_page(None)  # the client sends the failed batch again
        close.set()
        empires_server.crash_log_editor.join(10)
        empires_server.server_error_page(None)  # closed, a new failure opens it again
        close.set()

    assert len(opened) == 2
    # the editor opens the file the server's log is written to (save_engine's daiquiri File output)
    [log_file] = [handler.baseFilename for handler in logging.getLogger().handlers
                  if isinstance(handler, logging.handlers.WatchedFileHandler)]
    assert [os.path.abspath(kwargs["filename"]) for kwargs in opened] == [log_file, log_file]
