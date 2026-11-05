"""Fixes in test/server_setup_test.py and test/session_layer_test.py (keeps each file's line endings)."""


def edit(p, pairs):
    raw = open(p, "rb").read().decode("utf-8")
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    for old, new in pairs:
        assert t.count(old) == 1, (p, old[:80])
        t = t.replace(old, new)
    open(p, "wb").write((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))


edit("test/server_setup_test.py", [
    ('''    assert stored(server, sid) == {}
''', '''    assert stored(server, sid) is None  # the save is gone (a backup is kept: test_deleting_a_save_keeps_a_backup)
'''),
    ('''def test_the_save_cookie_can_be_replaced_by_the_pages_and_is_not_sent_by_other_sites(server):
    _, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    cookie = server.test_client().get("/home.html", headers={"Cookie": "session=" + sid}).headers["Set-Cookie"]
    flags = [part.strip().lower() for part in cookie.split(";")]

    assert flags[0] == "session=" + sid.lower()
''', '''def test_the_save_cookie_can_be_replaced_by_the_pages_and_is_not_sent_by_other_sites(server):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    edited = {"user_object": VALID_USER_OBJECT, "quests": []}
    response = client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "x"})  # changes the save
    flags = [part.strip().lower() for part in response.headers["Set-Cookie"].split(";")]

    assert response.status_code == 302 and flags[0] == "session=" + sid.lower()
'''),
    ('''FIVE_MB = 5 * 1024 * 1024  # the save editor takes a save game of up to 5 MB (commit "Fix request entity too large")


def test_the_save_editor_takes_a_form_of_5_mb_but_not_more(server):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    over = client.post("/save-editor", data={"savegame": "x" * (FIVE_MB + 1), "message": "big"})
    assert over.status_code == 413
    at = client.post("/save-editor", data={"savegame": "x" * FIVE_MB, "message": "big"})
''', '''# The save editor takes a form of up to 5 MB (commit 62d415f "Fix request entity too large"); its <form> is a plain
# POST (templates/save-editor.html), so the browser sends it urlencoded, and for that the limit is the whole body.
FIVE_MB = 5 * 1024 * 1024


def test_the_save_editor_takes_a_form_of_5_mb_but_not_more(server):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    rest = len("savegame=&message=big")
    over = client.post("/save-editor", data={"savegame": "x" * (FIVE_MB - rest + 1), "message": "big"})
    assert over.status_code == 413
    at = client.post("/save-editor", data={"savegame": "x" * (FIVE_MB - rest), "message": "big"})
'''),
    ('''def test_assets_are_served_without_the_save_and_the_gateways_with_it(server, monkeypatch):
    inner = server.session_interface.inner
''', '''def test_assets_are_served_without_the_save_and_the_gateways_with_it(server, monkeypatch):
    client, _ = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    inner = server.session_interface.inner
'''),
    ('''                        save_session(app, session, response))
    client, _ = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
''', '''                        save_session(app, session, response))
'''),
    ('''import pytest
from pyamf''', '''import json

import pytest
from pyamf'''),
])

edit("test/session_layer_test.py", [
    ('''    # the failed call's answer has the fields of every answer (those of the calls that worked), with no data
    assert set(answers[1]) == set(answers[0]) and answers[1]["data"] is None
''', '''    # the failed call's answer has the fields of every answer (those of the calls that worked) and errorData, no data
    assert set(answers[1]) == set(answers[0]) | {"errorData"} and answers[1]["data"] is None
'''),
    ('''    # the editor opens the file the server's log is written to (save_engine's daiquiri file output)
    [log_file] = [handler.baseFilename for handler in logging.getLogger().handlers
                  if isinstance(handler, logging.FileHandler)]
''', '''    # the editor opens the file the server's log is written to (save_engine's daiquiri File output)
    [log_file] = [handler.baseFilename for handler in logging.getLogger().handlers
                  if isinstance(handler, logging.handlers.WatchedFileHandler)]
'''),
    ('''import logging
''', '''import logging
import logging.handlers
'''),
])
print("ok")
