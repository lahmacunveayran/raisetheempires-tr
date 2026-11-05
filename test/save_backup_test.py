"""save_engine on its own: backups (what a backup holds, its dates, how many are kept), the id saves are backed up
under, the save game check, where save.db is, and the crash log. Expected values come from the input and from the
rule written next to each assert, not from save_engine's own constants."""
import copy
import json
import logging
import os
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask, session
from sqlalchemy.engine import make_url

import save_engine

app = Flask(__name__)
app.secret_key = "test"

with open(os.path.join(os.path.dirname(__file__), "init_user.json")) as f:
    INIT_USER = json.load(f)
T0 = 1_600_000_000.0  # a time in the past (Windows can not take timestamps near 1970 back)


class Clock:
    """save_engine's datetime with now() pinned to Clock.at (a timestamp)."""
    at = T0

    @classmethod
    def now(cls, tz=None):
        return datetime.fromtimestamp(cls.at, tz)


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(save_engine, "datetime", Clock)
    monkeypatch.setattr(Clock, "at", T0)
    return Clock


# What a backup must hold to give the save back: every part the save editor writes when it restores a backup
# (user_object, quests, battle, fleets, population, save_version: empires-server.py save_savegame), what the backup
# list shows of it (saved_on, save_version: format_backup_message), and the marks of where the save came from
# (saved: the cheats and edits done to it, original_save_version: the version it was started with).
KEPT = ("user_object", "quests", "battle", "fleets", "population", "saved", "saved_on", "save_version",
        "original_save_version")
# Parts of a save that are not backed up: the avatar, the last battle's context, the save's own id.
NOT_KEPT = ("profilePic", "last_battle", "session_id")


def full_save():
    values = {"user_object": copy.deepcopy(INIT_USER), "quests": [{"name": "Q0516", "complete": False}],
              "battle": [[10], None, [20], None], "fleets": {"fleet1_1": ["U01,10,0,0,0"]}, "population": 7,
              "saved": "seed", "saved_on": T0 - 500, "save_version": "0.08a", "original_save_version": "0.05a",
              "profilePic": "a.png", "last_battle": {"map": "camp001"}, "session_id": "session:other"}
    assert set(values) == set(KEPT) | set(NOT_KEPT)
    return values


def test_a_backup_holds_the_save_with_its_dates(clock):
    """create_backup: the backup holds the save as it was, with when that save was saved (saved_on) and when it was
    replaced (now: replaced_on), and the save is from now on saved at that time."""
    with app.test_request_context():
        session.update(full_save())
        session.sid = "abc"
        before = copy.deepcopy(dict(session))

        save_engine.create_backup("Level 5")

        [(backup_id, info)] = save_engine.list_backups(session)
        assert info == {"saved_on": T0 - 500, "replaced_on": T0, "save_version": "0.08a", "message": "Level 5"}
        backup = save_engine.load_backup(session, backup_id)
        assert backup == dict({k: before[k] for k in KEPT}, replaced_on=T0, message="Level 5")
        assert session["saved_on"] == T0


def test_each_backup_covers_the_time_from_the_one_before(clock):
    """saved_on - replaced_on of the backup list: the second backup holds the save that the first one replaced."""
    with app.test_request_context():
        session.update(full_save())
        session.sid = "abc"
        clock.at = T0 + 60
        save_engine.create_backup("first")
        clock.at = T0 + 120
        save_engine.create_backup("second")

        infos = [info for _, info in save_engine.list_backups(session)]
        assert [(i["message"], i["saved_on"], i["replaced_on"]) for i in infos] == \
            [("second", T0 + 60, T0 + 120), ("first", T0 - 500, T0 + 60)]


def test_a_save_without_a_version_is_listed_as_none():
    """store_backup keeps the version as text: a save of before versions were kept has the text 'None'."""
    with app.test_request_context():
        session["user_object"] = {}
        save_engine.create_backup("x")
        [(_, info)] = save_engine.list_backups(session)
        assert info["save_version"] == "None" and info["saved_on"] is None


def test_twenty_backups_are_kept_per_save():
    """At most 20 backups a save: since backups moved out of the save (the comment above MAX_BACKUPS) the save editor
    lists them all on one page, 20 was the number chosen for that list (save_engine, 'only the newest MAX_BACKUPS
    per save are kept'; the number itself has no other source). The oldest go first, other saves keep theirs."""
    with app.test_request_context():
        session["user_object"] = {"n": -1}
        session.sid = "other"
        save_engine.create_backup("other save")
        session.sid = "mine"
        for i in range(25):
            session["user_object"] = {"n": i}
            save_engine.create_backup("Level %d" % i)

        mine = save_engine.list_backups(session)
        assert [info["message"] for _, info in mine] == ["Level %d" % i for i in range(24, 4, -1)]
        assert len(mine) == 20
        assert save_engine.load_backup(session, mine[0][0])["user_object"] == {"n": 24}
        assert [info["message"] for _, info in save_engine.list_backups({"session_id": "other"})] == ["other save"]
        assert save_engine.load_backup({"session_id": "other"}, mine[0][0]) is None  # not its backup


def test_an_old_backup_chain_moves_out_without_the_chain():
    """move_nested_backups: each level of the chain (save["backup"]["backup"]...) becomes one backup of its own,
    without the levels below it; a level without a message gets an empty one."""
    save = {"session_id": "session:abc", "user_object": {"n": "now"}}
    save["backup"] = {"message": "newer", "user_object": {"n": 1},
                      "backup": {"user_object": {"n": 0}, "saved_on": T0}}

    assert save_engine.move_nested_backups(save) is True

    stored = [(info, save_engine.load_backup(save, i)) for i, info in save_engine.list_backups(save)]
    assert [info["message"] for info, _ in stored] == ["newer", ""]
    assert [backup for _, backup in stored] == [{"message": "newer", "user_object": {"n": 1}},
                                                {"user_object": {"n": 0}, "saved_on": T0}]
    assert stored[1][0]["saved_on"] == T0
    assert save == {"session_id": "session:abc", "user_object": {"n": "now"}}


def test_no_backups_before_backups_db_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(save_engine, "backup_db_path", lambda: str(tmp_path / "none" / "backups.db"))
    assert save_engine.list_backups({"session_id": "x"}) == []


@pytest.mark.parametrize("save,save_id", [
    (types.SimpleNamespace(sid="abc"), "abc"),  # the save of a request: flask-session's sid
    ({"session_id": "session:abc"}, "abc"),  # a save read from save.db: its record's id is "session:" + sid
    ({"session_id": "abc"}, "abc"),
    ({"session_id": "my:session:abc"}, "my:session:abc"),  # only a leading "session:" is the prefix
    ({}, "local"),  # no id at all
])
def test_the_id_backups_are_kept_under(save, save_id):
    assert save_engine._save_id(save) == save_id


VALID = {"user_object": {"userInfo": {"worldName": "W", "world": {"resources": {"coins": 10}}, "player": {
    "level": 5, "uid": 1, "xp": 0, "playerResourceType": 0, "socialXpGood": 0, "socialLevelGood": 1,
    "socialXpBad": 0, "socialLevelBad": 1}}}}
# (where, field, a wrong value): the types the home page and the friends list read (validate_save)
WRONG = [("player", "level", "5"), ("player", "level", None), ("player", "uid", "1"), ("userInfo", "worldName", 5),
         ("player", "xp", "0"), ("player", "playerResourceType", 0.5), ("resources", "coins", "10"),
         ("player", "socialXpGood", None), ("player", "socialLevelGood", 1.5), ("player", "socialXpBad", "0"),
         ("player", "socialLevelBad", "1")]


def place(save, where):
    info = save["user_object"]["userInfo"]
    return {"userInfo": info, "player": info["player"], "resources": info["world"]["resources"]}[where]


def test_a_complete_save_is_valid():
    assert save_engine.validate_save(VALID) is True
    floats = copy.deepcopy(VALID)
    place(floats, "player")["xp"] = 1.5
    place(floats, "resources")["coins"] = 2.5
    assert save_engine.validate_save(floats) is True


@pytest.mark.parametrize("where,field,value", WRONG, ids=[f + "=" + repr(v) for _, f, v in WRONG])
def test_one_wrong_field_makes_the_save_invalid(where, field, value):
    save = copy.deepcopy(VALID)
    place(save, where)[field] = value
    assert save_engine.validate_save(save) is False
    assert save_engine.validate_save(save, True) is False  # it has a user_object, so it is not a blank save


@pytest.mark.parametrize("where,field", sorted({(w, f) for w, f, _ in WRONG}))
def test_every_field_must_be_there(where, field):
    """A missing field is as wrong as a wrong one (validate_save looks a missing one up as {}, which is no number)."""
    save = copy.deepcopy(VALID)
    del place(save, where)[field]
    assert save_engine.validate_save(save) is False


def test_a_blank_save_is_only_valid_where_one_is_allowed():
    """validate_save(save, blank_allowed): a session that has no save game yet (no user_object) is fine for the pages
    that start a new one (home.html), not as a save game."""
    for blank in ({}, {"quests": []}):
        assert save_engine.validate_save(blank) is False
        assert save_engine.validate_save(blank, True) is True
    assert save_engine.validate_save({"user_object": {}}, True) is False


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@pytest.fixture
def folders(monkeypatch, tmp_path):
    """Running from source: the My Games folder of the ini is the source folder (RaiseTheEmpires.ini)."""
    root = tmp_path / "source"
    root.mkdir()
    monkeypatch.setattr(save_engine, "my_games_path", lambda: str(root))
    return root, root / "instance"


def uri_path(uri):
    assert uri.startswith("sqlite:///")
    return Path(make_url(uri).database)


def test_an_old_save_db_is_moved_to_the_instance_folder(folders):
    """save_database_uri: Flask now keeps the database in the instance folder; a save.db in the source folder is
    moved there, unchanged, and a copy is kept in backup-save-db."""
    root, instance = folders
    data = b"SQLite format 3\x00" + bytes(range(256)) * 4
    write(root / "save.db", data)

    uri = save_engine.save_database_uri(str(root), str(instance))

    assert uri_path(uri) == instance / "save.db"
    assert (instance / "save.db").read_bytes() == data
    assert not (root / "save.db").exists()
    assert (root / "backup-save-db" / "save.db").read_bytes() == data


def test_a_save_db_in_the_instance_folder_is_never_written_over(folders):
    root, instance = folders
    write(root / "save.db", b"old")
    write(instance / "save.db", b"new")

    uri = save_engine.save_database_uri(str(root), str(instance))

    assert uri_path(uri) == instance / "save.db"
    assert (instance / "save.db").read_bytes() == b"new"
    assert (root / "save.db").read_bytes() == b"old"  # left for the player to sort out (the warning)
    assert not (root / "backup-save-db").exists()


def test_a_new_install_from_source_uses_the_instance_folder(folders):
    root, instance = folders
    assert uri_path(save_engine.save_database_uri(str(root), str(instance))) == instance / "save.db"
    assert os.listdir(root) == []  # nothing made or moved


def test_an_install_keeps_save_db_in_my_games(monkeypatch, tmp_path):
    """Installed (the program folder is not My Games): save.db stays in My Games, nothing is moved."""
    my_games, program = tmp_path / "My Games", tmp_path / "program"
    write(my_games / "save.db", b"mine")
    program.mkdir()
    monkeypatch.setattr(save_engine, "my_games_path", lambda: str(my_games))

    uri = save_engine.save_database_uri(str(program), str(program / "instance"))

    assert uri_path(uri) == my_games / "save.db"
    assert (my_games / "save.db").read_bytes() == b"mine"
    assert sorted(os.listdir(tmp_path)) == ["My Games", "program"] and os.listdir(program) == []


def test_the_frozen_program_runs_from_its_exe_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "RaiseTheEmpires.exe"))
    assert save_engine.base_path() == tmp_path / "dist"
    monkeypatch.setattr(sys, "frozen", False)
    assert save_engine.base_path() == Path(save_engine.__file__).parent


def log_file():
    [handler] = [h for h in logging.getLogger().handlers  # pytest adds a file handler of its own
                 if isinstance(h, logging.FileHandler) and not type(h).__module__.startswith("_pytest")]
    return handler.baseFilename


def test_a_crash_opens_the_log_the_server_writes(monkeypatch, caplog):
    """exception_handler: an uncaught error is logged, and with the crash log on the log file is opened in an editor:
    the file the server's log goes to (daiquiri's file output)."""
    opened = []
    monkeypatch.setattr(save_engine.editor, "edit", lambda **kwargs: opened.append(kwargs))
    save_engine.set_crash_log(True)
    try:
        raise ValueError("boom")
    except ValueError:
        error = sys.exc_info()
    with caplog.at_level(logging.ERROR):
        save_engine.exception_handler(*error)

    assert [os.path.abspath(o["filename"]) for o in opened] == [log_file()]
    assert os.path.basename(log_file()) == "log.txt"
    assert [(r.levelno, r.getMessage(), r.exc_info[1]) for r in caplog.records] == \
        [(logging.ERROR, "Uncaught exception", error[1])]

    save_engine.set_crash_log(False)
    opened.clear()
    save_engine.exception_handler(*error)
    assert opened == []


def test_ctrl_c_is_not_a_crash(monkeypatch, caplog):
    opened, default = [], []
    monkeypatch.setattr(save_engine.editor, "edit", lambda **kwargs: opened.append(kwargs))
    monkeypatch.setattr(sys, "__excepthook__", lambda *args: default.append(args))
    save_engine.set_crash_log(True)
    with caplog.at_level(logging.ERROR):
        save_engine.exception_handler(KeyboardInterrupt, KeyboardInterrupt(), None)

    assert opened == [] and caplog.records == []
    assert len(default) == 1


def test_uncaught_errors_go_to_the_crash_handler():
    assert sys.excepthook is save_engine.exception_handler
