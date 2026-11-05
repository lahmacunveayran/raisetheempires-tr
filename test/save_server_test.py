"""The routes that change the save game and the save editor, through the real server: Flask's routes, flask-session
with SQLAlchemy and msgspec, save.db in a temporary folder, the way empires-server.py sets them up when it runs.

The expected values are written out here from the input and from what each route is for (its docstring or comment
in empires-server.py), never read from the server's own lists (SAVE_CHANGING_PATH_PREFIXES, BACKUP_KEYS)."""
import copy
import html
import json
import os
import re
from datetime import datetime

import pytest

empires_server = __import__('empires-server')
import logger
import save_engine
from battle_engine import BattleContext

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)

FOREIGN = ({"Referer": "https://evil.example/page"}, {"Origin": "https://evil.example"}, {"Origin": "null"})
T0 = 1_600_000_000.0  # a time in the past (Windows can not take timestamps near 1970 back)
SAME_SITE = {"Referer": "http://localhost/save-editor"}  # the test client's host is localhost


def _forget_save_database(app):
    """Undo db.init_app / sess.init_app: both can only be done once for an app (a second time raises), so a module
    that sets the server up must take it down again for the next one (test/session_layer_test.py sets it up too)."""
    db = empires_server.db
    if "sqlalchemy" in app.extensions:
        for engine in db._app_engines.pop(app, {}).values():
            engine.dispose()
        del app.extensions["sqlalchemy"]
        while db._teardown_session in app.teardown_appcontext_funcs:
            app.teardown_appcontext_funcs.remove(db._teardown_session)
    table = db.metadata.tables.get("sessions")
    if table is not None:
        db.metadata.remove(table)


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    app = empires_server.app
    _forget_save_database(app)  # a module before this one may have left its set up behind
    saved = app.session_interface, app.config["SQLALCHEMY_DATABASE_URI"], app._got_first_request
    app._got_first_request = False  # the server sets up before its first request
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + (tmp_path_factory.mktemp("saves") / "save.db").as_posix()
    empires_server.db.init_app(app)
    empires_server.sess.init_app(app)
    app.session_interface = empires_server.AssetSkippingSessionInterface(app.session_interface)
    yield app
    _forget_save_database(app)
    app.session_interface, app.config["SQLALCHEMY_DATABASE_URI"], app._got_first_request = saved


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(logger.socketio, "emit", lambda *args, **kwargs: None)
    monkeypatch.setattr(empires_server.settings, "crash_log", False)
    monkeypatch.setattr(empires_server, "get_saves", lambda: [])  # pages list the other saves; not these tests'


class Clock:
    """save_engine's datetime with now() pinned to Clock.at (a timestamp)."""
    at = 1_700_000_000.0

    @classmethod
    def now(cls, tz=None):
        return datetime.fromtimestamp(cls.at, tz)

    fromtimestamp = staticmethod(datetime.fromtimestamp)


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(save_engine, "datetime", Clock)
    monkeypatch.setattr(Clock, "at", 1_700_000_000.0)
    return Clock


def new_save(app, **values):
    client = app.test_client()
    with client.session_transaction() as save:
        save.update(values)
    return client, client.get_cookie("session").value


def record(app, sid):
    with app.app_context():
        found = app.session_interface.sql_session_model.query.filter_by(session_id="session:" + sid).first()
        return None if found is None else bytes(found.data)


def stored(app, sid):
    data = record(app, sid)
    with app.app_context():
        return None if data is None else app.session_interface.serializer.decode(data)


def backups(sid):
    """[(id, info)] newest first, of the save with this session id, as save_engine lists them."""
    return save_engine.list_backups({"session_id": "session:" + sid})


def a_save(**extra):
    """A save the routes below can all work on: a campaign map in play (deprogress), quests (complete, remove), an old
    backup chain in the save (the save editor moves it out)."""
    user_object = copy.deepcopy(INIT_USER)
    user_object["userInfo"]["worldName"] = "Mine"
    user_object["userInfo"]["world"]["campaign"]["active"] = {"camp001": {"status": 2 << 20, "fleets": []}}
    save = dict(user_object=user_object, quests=[{"name": "Q0516", "complete": False, "expired": False,
                                                  "progress": [0], "completedTasks": 0}],
                battle=None, fleets={}, population=None, saved="", save_version=empires_server.version,
                original_save_version="0.05a",
                backup={"message": "old chain", "user_object": {"old": True}})
    save.update(extra)
    if save["backup"] is None:
        del save["backup"]
    return save


def edited_save_form():
    edited = {k: v for k, v in a_save().items() if k != "backup"}
    edited["user_object"]["userInfo"]["worldName"] = "Edited"
    return {"savegame": json.dumps(edited), "message": "x"}


# Routes that change or replace the save game, or hand out what lets another page do that: each is a plain link on
# the server's own pages, so a request from another site is never legitimate (empires-server.py, the comment above
# its list). (method, url of a request that changes this test's save, its rule in app.url_map)
SAVE_CHANGING = [
    ("GET", "/wipe_session", "/wipe_session"),  # deletes the save
    ("POST", "/wipe_session", "/wipe_session"),
    ("GET", "/list_session", "/list_session"),  # the session ids of all saves are their cookies
    ("GET", "/gazillionaire", "/gazillionaire"),  # cheat: cash
    ("GET", "/deprogress", "/deprogress"),  # cheat: campaign map back
    ("GET", "/seed/w/5/z/6", "/seed/w/<int:w>/z/<int:z>"),
    ("GET", "/patch/user_object/userInfo/worldName/empty-dict", "/patch/<path:path>/empty-dict"),
    ("GET", "/patch/user_object/userInfo/worldName/empty-list", "/patch/<path:path>/empty-list"),
    ("GET", "/patch/user_object/userInfo/worldName/none", "/patch/<path:path>/none"),
    ("GET", "/patch/user_object/userInfo/worldName/string/Evil", "/patch/<path:path>/string/<value>"),
    ("GET", "/patch/user_object/userInfo/player/cash/int/99999", "/patch/<path:path>/int/<int:value>"),
    ("GET", "/patch/user_object/userInfo/player/expansions/data/list/index/0/string/x",
     "/patch/<path:path>/list/index/<int:i>/string/<value>"),
    ("GET", "/patch/user_object/userInfo/player/expansions/data/list/index/0/int/7",
     "/patch/<path:path>/list/index/<int:i>/int/<int:value>"),
    ("GET", "/unlock_quest/Q0531", "/unlock_quest/<value>"),
    ("GET", "/complete_quest/Q0516", "/complete_quest/<value>"),
    ("GET", "/remove_quest/Q0516", "/remove_quest/<value>"),
    ("GET", "/save-editor", "/save-editor"),  # moves the backup chain out of the save; shows the whole save
    ("POST", "/save-editor", "/save-editor"),  # replaces the save
    ("GET", "/chooseavatar/evil.png", "/chooseavatar/<path:path>"),
    ("GET", "/login.html", "/login.html"),  # lists the saves to switch to, by their session ids
    ("GET", "/new.html", "/new.html"),  # starts a new save
]
# Routes that only read: pages that show the save, the game's files and assets.
NOT_SAVE_CHANGING = {
    "/static/<path:filename>", "/", "/home.html", "/ruffle.html", "/nodebug.html", "/127.0.0.1record_stats.php",
    "/files/empire-s.assets.zgncdn.com/assets/109338/ZGame.109338.swf", "/gameSettings.xml",
    "/127.0.0.1gameSettings.xml", "/127.0.0.1en_US.xml", "/127.0.0.1questSettings.xml", "/releases.html",
    "/friends.html", "/changelog.txt", "/img/<path:path>", "/js/<path:path>", "/css/<path:path>",
    "/nullassets/<path:path>", "/assets/<path:path>", "/language_editor",
}
# The game's own calls change the save too, but come from the Flash/Ruffle client, not from a link: they are not
# checked for Referer/Origin; the session cookie being SameSite=Strict keeps other sites' requests from the save.
GAME_CALLS = {"/127.0.0.1flashservices/gateway.php",
              "/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php"}


def send(client, method, url, headers=None):
    data = edited_save_form() if (method, url) == ("POST", "/save-editor") else None
    return client.open(url, method=method, headers=headers or {}, data=data)


def test_every_route_is_either_save_changing_or_not():
    """A new route must be put in one of the lists above: then it is decided whether other sites may call it."""
    rules = {rule.rule for rule in empires_server.app.url_map.iter_rules()}
    changing = {rule for _, _, rule in SAVE_CHANGING}
    assert not changing & NOT_SAVE_CHANGING and not changing & GAME_CALLS and not NOT_SAVE_CHANGING & GAME_CALLS
    assert rules == changing | NOT_SAVE_CHANGING | GAME_CALLS


@pytest.mark.parametrize("method,url,rule", SAVE_CHANGING, ids=[m + " " + u for m, u, _ in SAVE_CHANGING])
def test_cross_site_requests_change_nothing(server, method, url, rule):
    for headers in FOREIGN:
        client, sid = new_save(server, **a_save())
        before = record(server, sid)

        response = send(client, method, url, headers)

        assert response.status_code == 403, headers
        assert record(server, sid) == before, headers  # byte for byte
        assert backups(sid) == [], headers  # every save changing route backs the save up first


@pytest.mark.parametrize("method,url,rule", SAVE_CHANGING, ids=[m + " " + u for m, u, _ in SAVE_CHANGING])
def test_requests_from_the_servers_own_pages_get_through(server, method, url, rule):
    """The other half of the test above: the 403 there comes from the site check, not from the route."""
    for headers in (SAME_SITE, {}):
        client, sid = new_save(server, **a_save())
        response = send(client, method, url, headers)
        assert response.status_code in (200, 302), (headers, response.status_code)


def test_deleting_the_save_backs_it_up_and_goes_to_the_login_page(server, clock):
    client, sid = new_save(server, **a_save(saved_on=T0))
    before = stored(server, sid)

    response = client.post("/wipe_session")

    assert response.status_code == 302 and response.headers["Location"] == "/login.html"
    assert "user_object" not in (stored(server, sid) or {})
    [(backup_id, info)] = backups(sid)
    assert info == {"saved_on": T0, "replaced_on": clock.at, "save_version": empires_server.version,
                    "message": "Before deleting the save game"}
    assert save_engine.load_backup({"session_id": "session:" + sid}, backup_id)["user_object"] == \
        before["user_object"]


def editor_page(client):
    return client.get("/save-editor").get_data(as_text=True)


def shown_save(page):
    textarea = re.search(r'<textarea rows="30" cols="135" name="savegame" >(.*?)</textarea>', page, re.S)
    return json.loads(html.unescape(textarea.group(1)))


def test_the_save_editor_shows_every_part_of_the_save(server):
    """save_editor: the save as JSON, one key for each part the editor can write back or that tells where the save
    came from; a value JSON can't hold is shown as '<not serializable>'."""
    values = {"user_object": copy.deepcopy(INIT_USER), "profilePic": "8_HansCP_100.png",
              "quests": [{"name": "Q0516", "complete": False}], "battle": [[10, 20], None, [30], None],
              "last_battle": BattleContext(map_name="camp001", island=2), "fleets": {"fleet1_1": ["U01,10,0,0,0"]},
              "population": 12, "saved": "seededit", "save_version": "0.08a", "original_save_version": "0.05a"}
    client, _ = new_save(server, **values, other_key="not shown")

    shown = shown_save(editor_page(client))

    assert shown == dict(values, last_battle="<not serializable>")


def test_the_save_editor_says_when_the_save_is_corrupt(server):
    """save-editor.html shows 'Your savegame is corrupt.' when validate_save fails."""
    good, _ = new_save(server, user_object=copy.deepcopy(INIT_USER), quests=[])
    bad, _ = new_save(server, user_object={"userInfo": {"worldName": "No player"}}, quests=[])

    assert "Your savegame is corrupt." not in editor_page(good)
    assert "Your savegame is corrupt." in editor_page(bad)


def test_the_save_editor_links_the_quests_by_their_state(server):
    """Unlock: quests the save does not have; complete: its open quests; remove: its open, then its done quests."""
    client, _ = new_save(server, user_object=copy.deepcopy(INIT_USER), quests=[
        {"name": "Q0516", "complete": False}, {"name": "Q0531", "complete": True}])
    page = editor_page(client)

    assert re.findall(r'href="/complete_quest/(\w+)"', page) == ["Q0516"]
    assert re.findall(r'href="/remove_quest/(\w+)"', page) == ["Q0516", "Q0531"]
    unlockable = re.findall(r'href="/unlock_quest/(\w+)"', page)
    assert unlockable and not {"Q0516", "Q0531"} & set(unlockable)


def test_the_save_editor_writes_what_it_was_given(server, clock):
    """save_savegame: backs the save up ("before <message>"), marks it as edited, then writes the edited parts;
    an avatar is only taken over when the save and the edit both have one."""
    client, sid = new_save(server, **a_save(profilePic="a.png", saved="seed", saved_on=T0, backup=None))
    before = stored(server, sid)
    edited = {"user_object": copy.deepcopy(INIT_USER), "profilePic": "b.png", "quests": [{"name": "Q0531"}],
              "battle": [[1], None, [2], None], "fleets": {"fleet3_1": ["U02,5,0,0,0"]}, "population": 3,
              "save_version": "edited version", "saved": "not taken", "original_save_version": "not taken"}
    edited["user_object"]["userInfo"]["worldName"] = "Edited"

    response = client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "my edit"})

    assert response.status_code == 302 and response.headers["Location"] == "/home.html"
    save = stored(server, sid)
    for key in ("user_object", "profilePic", "quests", "battle", "fleets", "population", "save_version"):
        assert save[key] == edited[key], key
    assert save["saved"] == "seed" + "edit"
    assert save["original_save_version"] == before["original_save_version"]
    assert save["saved_on"] == clock.at
    [(backup_id, info)] = backups(sid)
    assert info == {"saved_on": T0, "replaced_on": clock.at, "save_version": empires_server.version,
                    "message": "before my edit"}
    backup = save_engine.load_backup({"session_id": "session:" + sid}, backup_id)
    assert (backup["user_object"], backup["quests"]) == (before["user_object"], before["quests"])


def test_an_edit_without_an_avatar_keeps_the_saves(server):
    client, sid = new_save(server, **a_save(profilePic="a.png", backup=None))
    edited = {"user_object": copy.deepcopy(INIT_USER), "quests": []}

    assert client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "x"}).status_code == 302
    assert stored(server, sid)["profilePic"] == "a.png"


def local(timestamp):  # format_backup_message: the dates as the backup list shows them
    return datetime.fromtimestamp(timestamp).strftime("%d %b %Y %H:%M:%S")


def test_a_backup_restored_in_the_save_editor_brings_the_save_back(server, clock):
    """Round trip: a save, backed up by a cheat (seed), then edited, then restored from the backup list: every part
    the editor writes comes back as it was; the restore itself is backed up first."""
    first = a_save(battle=[[10, 20], None, [30], None], fleets={"fleet1_1": ["U01,10,0,0,0"]}, population=7,
                   save_version="0.08a.first", saved="", saved_on=T0, backup=None,
                   quests=[{"name": "Q0516", "complete": False, "expired": False, "progress": [0],
                            "completedTasks": 0}])
    client, sid = new_save(server, **first)
    clock.at = T0 + 1000
    assert client.get("/seed/w/5/z/6").status_code == 302  # backup 1: the first save
    clock.at = T0 + 2000
    edited = {"user_object": copy.deepcopy(INIT_USER), "quests": [], "battle": None, "fleets": {}, "population": 1,
              "save_version": "edited"}
    assert client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "e"}).status_code == 302
    page = editor_page(client)
    listed = re.findall(r"(\d\d \w\w\w \d{4} [\d:]+ - \d\d \w\w\w \d{4} [\d:]+ @\S* .*?) <a", page)
    # newest first: the edit's backup (the save after the seed change), then the seed's (the first save)
    assert listed == [local(T0 + 1000) + " - " + local(T0 + 2000) + " @0.08a.first before e",
                      local(T0) + " - " + local(T0 + 1000) + " @0.08a.first seed"]
    assert re.findall(r'name="(restore\d+)"', page) == ["restore0", "restore1"]
    clock.at = T0 + 3000

    response = client.post("/save-editor", data={"restore1": "Restore this backup"})

    assert response.status_code == 302
    save = stored(server, sid)
    for key in ("user_object", "quests", "battle", "fleets", "population", "save_version"):
        assert save[key] == first[key], key
    assert save["saved"] == "seed" + "edit" + "edit"
    infos = [info for _, info in backups(sid)]
    assert infos[0] == {"saved_on": T0 + 2000, "replaced_on": T0 + 3000, "save_version": "edited",
                        "message": 'Revert to backup "' + listed[1] + '"'}
    assert len(infos) == 3


def test_restoring_a_backup_that_is_not_there_changes_nothing(server):
    client, sid = new_save(server, **a_save(backup=None))
    assert client.get("/gazillionaire").status_code == 302  # one backup: restore0
    before = record(server, sid)

    assert client.post("/save-editor", data={"restore1": "Restore this backup"}).status_code == 404
    assert record(server, sid) == before
    assert len(backups(sid)) == 1


def test_a_backup_made_in_a_request_is_found_from_the_saves_list(server):
    """_save_id: a request's save is backed up under its session id; the same save read from save.db (get_saves,
    where it is "session:<id>") finds those backups, and a save without user_object is not a save game."""
    client, sid = new_save(server, **a_save(backup=None))
    new_save(server, fleets={})  # no user_object: not listed
    assert client.get("/gazillionaire").status_code == 302

    with server.app_context():
        saves = save_engine.get_saves()
    [save] = [s for s in saves if s["session_id"] == "session:" + sid]
    assert [info["message"] for _, info in save_engine.list_backups(save)] == ["gazillionaire cheat"]
    assert all("user_object" in s for s in saves)
