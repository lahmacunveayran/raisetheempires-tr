"""Tests through the server's real save game layer: flask-session with SQLAlchemy and msgspec, the way
empires-server.py sets it up when it runs, with save.db in a temporary folder."""
import json
import pickle
import sqlite3
import threading
import types

import pyamf
import pytest
from pyamf import remoting

empires_server = __import__('empires-server')
import game_settings
import logger
import save_engine
import save_migration

GATEWAY = "/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php"
VALID_USER_OBJECT = {"userInfo": {"worldName": "Test", "world": {"resources": {"coins": 10}}, "player": {
    "level": 5, "uid": 1, "xp": 0, "playerResourceType": 0, "socialXpGood": 0, "socialLevelGood": 1,
    "socialXpBad": 0, "socialLevelBad": 1}}}


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    app = empires_server.app
    original_interface = app.session_interface
    app._got_first_request = False  # other tests already sent requests to it; the server sets up before its first
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + (tmp_path_factory.mktemp("saves") / "save.db").as_posix()
    empires_server.db.init_app(app)
    empires_server.sess.init_app(app)
    app.session_interface = empires_server.AssetSkippingSessionInterface(app.session_interface)
    yield app
    app.session_interface = original_interface


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


def batch(client, *calls):
    """Sends calls [(functionName, params), ...] like the client does, returns the answers to the calls."""
    envelope = remoting.Envelope(3)
    body = [{"flashRevision": None}, [{"transaction": None, "sequence": i + 1, "stamp": 0, "params": params,
                                       "functionName": name} for i, (name, params) in enumerate(calls)], 0]
    envelope.bodies = [("/1", remoting.Request("BaseService.dispatchBatch", body=body, envelope=envelope))]
    response = client.post(GATEWAY, data=remoting.encode(envelope).getvalue(), content_type="application/x-amf")
    assert response.content_type == "application/x-amf"
    return remoting.decode(response.data).bodies[0][1].body["data"]


def fleet(name):
    return {"name": name, "units": ["U01,10,0,0,0"]}


def test_a_failing_call_is_undone_and_the_other_calls_are_kept(server, monkeypatch):
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
                    ("WorldService.addFleet", [fleet("last")]))

    assert [answer["errorType"] for answer in answers] == [0, empires_server.CALL_FAILED, 0]
    assert answers[1]["errorData"] == "WorldService.addFleet"
    assert set(stored(server, sid)["fleets"]) == {"first", "last"}
    assert "changed_by_failed_call" not in stored(server, other_sid)


def test_overlapping_requests_of_one_save_wait_for_each_other(server, monkeypatch):
    client, sid = new_save(server, fleets={})
    other_client = server.test_client()
    other_client.set_cookie("session", sid)
    slow_started, go_on, fast_done = threading.Event(), threading.Event(), threading.Event()
    add_fleet = empires_server.add_fleet_response

    def slow_add_fleet(param):
        if param["name"] == "slow":
            slow_started.set()
            go_on.wait(10)
        return add_fleet(param)

    monkeypatch.setattr(empires_server, "add_fleet_response", slow_add_fleet)
    slow = threading.Thread(target=batch, args=(client, ("WorldService.addFleet", [fleet("slow")])))
    fast = threading.Thread(target=lambda: (batch(other_client, ("WorldService.addFleet", [fleet("fast")])),
                                            fast_done.set()))
    slow.start()
    assert slow_started.wait(10)
    fast.start()
    assert not fast_done.wait(0.5)  # the save is in use by the slow request
    go_on.set()
    slow.join(10)
    fast.join(10)

    assert fast_done.is_set()
    assert set(stored(server, sid)["fleets"]) == {"slow", "fast"}  # without waiting, slow writes over fast's fleet


def test_answers_only_ip_addresses_and_localhost(server):
    client = server.test_client()
    for host in ("127.0.0.1:5005", "localhost:5005", "192.168.1.20:5005", "[::1]:5005", "localhost"):
        assert client.get("/127.0.0.1record_stats.php", headers={"Host": host}).status_code == 204, host
    for host in ("evil.example:5005", "evil.example", "127.0.0.1.evil.example"):
        assert client.get("/127.0.0.1record_stats.php", headers={"Host": host}).status_code == 403, host


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

    assert not raw_record(server, "pickled").startswith(b"\x80")
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


def test_save_editor_opens_for_a_new_save_and_old_backups(server):
    assert server.test_client().get("/save-editor").status_code == 200
    assert empires_server.format_backup_message({"saved_on": None, "replaced_on": None})


@pytest.mark.parametrize("modded", [b"<settings/>", "<settings/>"])  # a replaced file, an xmldiff
def test_mods_of_the_settings_files_are_served(server, monkeypatch, modded):
    for path, route in (("assets/29oct2012/gameSettings_with_fixes.xml", "/gameSettings.xml"),
                        ("assets/29oct2012/questSettings_with_fixes.xml", "/127.0.0.1questSettings.xml")):
        monkeypatch.setitem(empires_server.mod_engine.mod, path, lambda: modded)
        response = server.test_client().get(route)
        assert response.status_code == 200, route
        assert b"<settings" in response.data, route


def test_crew_from_another_local_save(server, monkeypatch):
    building = {}
    monkeypatch.setattr(empires_server, "lookup_object", lambda building_id: building)
    monkeypatch.setattr(empires_server, "lookup_crew_template",
                        lambda name: {"-numUnbuyableSlots": "0", "position": [{}, {}]})
    with server.test_request_context():
        empires_server.crew_request_response([[2681928178598866.0], 10003, "Parliament", "crew"])

    assert building["crewInfo"] == ["2681928178598866"]  # not in allies/, and its id came as a double


def test_list_of_a_missing_object_can_be_logged(monkeypatch):
    emitted = []
    monkeypatch.setattr(logger.socketio, "emit", lambda *args: emitted.append(args))
    logger.report_world_log.__wrapped__("list", [], {}, 1, "/1", None, 0)  # without never_fails

    assert emitted[0][1][1] == "response"


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


def test_world_names_cannot_end_the_home_page_script():
    text = empires_server.script_json([{"name": "</script><b>x</b>"}])

    assert "</" not in text
    assert json.loads(text) == [{"name": "</script><b>x</b>"}]


def test_every_path_checks_the_host_also_socketio():
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    client = Client(empires_server.KnownHostsOnly(Response("ok")))  # around Flask-SocketIO's middleware in the server

    assert client.get("/socket.io/?EIO=4&transport=polling", headers={"Host": "evil.example:5005"}).status_code == 403
    assert client.get("/socket.io/?EIO=4&transport=polling", headers={"Host": "127.0.0.1:5005"}).status_code == 200


def test_a_call_that_leaves_an_unsaveable_value_is_undone(server, monkeypatch):
    client, sid = new_save(server, fleets={})
    add_fleet = empires_server.add_fleet_response

    def add_unsaveable_fleet(param):
        if param["name"] == "bad":
            empires_server.session["fleets"]["bad"] = object()
        return add_fleet(param) if param["name"] != "bad" else empires_server.dummy_response()

    monkeypatch.setattr(empires_server, "add_fleet_response", add_unsaveable_fleet)
    answers = batch(client, ("WorldService.addFleet", [fleet("bad")]), ("WorldService.addFleet", [fleet("good")]))

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
