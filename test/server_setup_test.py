"""The server as configure_app sets it up (the `server` fixture of conftest.py): what it answers to requests from other
hosts and sites, the error page of a request that fails outside a call, the save cookie, the form size limit and which
requests leave the save alone."""
import json

import pytest
from pyamf import remoting

from session_layer_test import GATEWAY, RUFFLE_GATEWAY, VALID_USER_OBJECT, batch, fleet, new_save, raw_record, stored

empires_server = __import__('empires-server')

SOCKET_IO = "/socket.io/?EIO=4&transport=polling"  # the log page's Socket.IO (templates/js), answered before Flask


def test_the_server_refuses_other_hosts_before_flask_and_socketio(server):
    client = server.test_client()
    for path in ("/", "/home.html", SOCKET_IO):
        response = client.get(path, headers={"Host": "evil.example"})
        # KnownHostsOnly answers it, around everything: a plain text 403 (Flask's own check would answer in HTML)
        assert (response.status_code, response.mimetype, response.data) == (403, "text/plain", b"Unknown host"), path
    # and behind it the Socket.IO middleware answers its path (Flask has no such route: it would be a 404)
    assert client.get(SOCKET_IO, headers={"Host": "127.0.0.1:5005"}).status_code == 200


def test_flask_itself_also_refuses_other_hosts():
    """reject_unknown_hosts, for the app without the middleware in front (as when it is used in the tests)."""
    response = empires_server.app.test_client().get("/", headers={"Host": "evil.example"})
    assert (response.status_code, response.get_data(as_text=True)) == (403, "Unknown host")


# The routes of the server's own pages that change or replace the save (the links of templates/*.html and the save
# editor's form), written out here: a page of another site must not reach any of them.
SAVE_CHANGING_REQUESTS = [("GET", "/wipe_session"), ("POST", "/wipe_session"), ("GET", "/list_session"),
                          ("GET", "/gazillionaire"), ("GET", "/deprogress"), ("GET", "/seed/w/1/z/2"),
                          ("GET", "/patch/userInfo/worldName/string/x"), ("GET", "/unlock_quest/Q0516"),
                          ("GET", "/complete_quest/Q0516"), ("GET", "/remove_quest/Q0516"),
                          ("POST", "/save-editor"), ("GET", "/chooseavatar/img/avatars/a.png"),
                          ("GET", "/login.html"), ("GET", "/new.html")]


@pytest.mark.parametrize("method, path", SAVE_CHANGING_REQUESTS)
def test_requests_of_other_sites_change_no_save(server, method, path):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[{"name": "Q0516", "complete": False}])
    before = raw_record(server, sid)
    response = client.open(path, method=method, headers={"Referer": "https://evil.example/page"})

    assert (response.status_code, response.get_data(as_text=True)) == (403, "Cross-site request blocked")
    assert raw_record(server, sid) == before


def test_deleting_a_save_goes_to_the_login_page(server):
    """After the save is deleted the player picks or starts another one on /login.html, as templates/js/session.js
    does after it clears the cookie (location.href = "/login.html")."""
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    response = client.get("/wipe_session")

    assert response.status_code == 302 and response.headers["Location"] == "/login.html"
    assert stored(server, sid) is None  # the save is gone (a backup is kept: test_deleting_a_save_keeps_a_backup)


def test_the_save_cookie_can_be_replaced_by_the_pages_and_is_not_sent_by_other_sites(server):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    edited = {"user_object": VALID_USER_OBJECT, "quests": []}
    response = client.post("/save-editor", data={"savegame": json.dumps(edited), "message": "x"})  # changes the save
    flags = [part.strip().lower() for part in response.headers["Set-Cookie"].split(";")]

    assert response.status_code == 302 and flags[0] == "session=" + sid.lower()
    # templates/js/session.js switches and clears saves with document.cookie, a script can't touch an HttpOnly cookie
    assert "httponly" not in flags
    assert "samesite=strict" in flags  # never sent along with a request another site starts (see SAVE_CHANGING...)


# The save editor takes a form of up to 5 MB (commit 62d415f "Fix request entity too large"); its <form> is a plain
# POST (templates/save-editor.html), so the browser sends it urlencoded, and for that the limit is the whole body.
FIVE_MB = 5 * 1024 * 1024


def test_the_save_editor_takes_a_form_of_5_mb_but_not_more(server):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    rest = len("savegame=&message=big")
    over = client.post("/save-editor", data={"savegame": "x" * (FIVE_MB - rest + 1), "message": "big"})
    assert over.status_code == 413
    at = client.post("/save-editor", data={"savegame": "x" * (FIVE_MB - rest), "message": "big"})
    assert at.status_code == 400 and at.get_data(as_text=True).startswith("Not saved")  # read, it is not JSON
    assert stored(server, sid)["user_object"] == VALID_USER_OBJECT


# What the game and its pages load besides the gateway, one of each kind: the save is not read for them (and they do
# not wait for the save's lock): templates/ (img, js, css), the game's swf and its assets (Flash: /nullassets/,
# Ruffle: /assets/), the settings files (Flash: /gameSettings.xml, Ruffle: /127.0.0.1...), the browser's favicon
ASSET_REQUESTS = ["/img/Coins_96.png", "/js/session.js", "/css/buttons.css",
                  "/nullassets/GeneralAssetGroup_UI.swf", "/assets/GeneralAssetGroup_UI.swf",
                  "/127.0.0.1en_US.xml", "/gameSettings.xml", "/changelog.txt", "/favicon.ico",
                  "/files/empire-s.assets.zgncdn.com/assets/109338/ZGame.109338.swf"]


def test_assets_are_served_without_the_save_and_the_gateways_with_it(server, monkeypatch):
    client, _ = new_save(server, user_object=VALID_USER_OBJECT, quests=[])
    inner = server.session_interface.inner
    opened, saved = [], []
    open_session, save_session = inner.open_session, inner.save_session
    monkeypatch.setattr(inner, "open_session", lambda app, request: opened.append(request.path) or
                        open_session(app, request))
    monkeypatch.setattr(inner, "save_session", lambda app, session, response: saved.append(1) or
                        save_session(app, session, response))
    for path in ASSET_REQUESTS:
        assert client.get(path).status_code in (200, 404), path  # 404: favicon.ico, the server has none
    assert (opened, saved) == ([], [])

    for gateway in (GATEWAY, RUFFLE_GATEWAY):
        batch(client, ("UserService.publishUserAction", [{}]), gateway=gateway)
    assert opened == [GATEWAY, RUFFLE_GATEWAY] and len(saved) == 2


@pytest.mark.parametrize("gateway", [GATEWAY, RUFFLE_GATEWAY], ids=["flash", "ruffle"])
def test_a_broken_request_gets_the_error_page_and_changes_no_save(server, gateway):
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[], fleets={})
    before = raw_record(server, sid)
    response = client.post(gateway, data=b"not an AMF message", content_type="application/x-amf")

    # server_error_page, the answer to any request that fails (errorhandler(500)), not Flask's own error page
    assert response.get_data(as_text=True) == "It went wrong"
    assert raw_record(server, sid) == before


@pytest.mark.parametrize("gateway", [GATEWAY, RUFFLE_GATEWAY], ids=["flash", "ruffle"])
def test_a_batch_whose_answer_fails_changes_no_save(server, monkeypatch, gateway):
    """transactional_session: a call that worked but whose answer can't be sent fails the whole request after the
    call changed the save: the client gets the error page, so the save must stay as it was."""
    client, sid = new_save(server, user_object=VALID_USER_OBJECT, quests=[], fleets={})
    before = raw_record(server, sid)
    add_fleet = empires_server.add_fleet_response

    def add_fleet_with_an_answer_amf_cannot_hold(param):
        return dict(add_fleet(param), data={1, 2})  # a set: pyamf can't encode it

    monkeypatch.setattr(empires_server, "add_fleet_response", add_fleet_with_an_answer_amf_cannot_hold)
    envelope = remoting.Envelope(3)
    body = [{"flashRevision": None}, [{"transaction": None, "sequence": 1, "stamp": 0, "params": [fleet("lost")],
                                       "functionName": "WorldService.addFleet"}], 0]
    envelope.bodies = [("/1", remoting.Request("BaseService.dispatchBatch", body=body, envelope=envelope))]
    response = client.post(gateway, data=remoting.encode(envelope).getvalue(), content_type="application/x-amf")

    assert response.get_data(as_text=True) == "It went wrong"
    assert raw_record(server, sid) == before
