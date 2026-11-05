"""Edits test/session_layer_test.py keeping its CRLF line endings."""
p = "test/session_layer_test.py"
b = open(p, "rb").read().decode("utf-8")
assert "\r\n" in b
t = b.replace("\r\n", "\n")


def rep(old, new):
    global t
    assert t.count(old) == 1, old[:80]
    t = t.replace(old, new)


rep('''"""Tests through the server's real save game layer: flask-session with SQLAlchemy and msgspec, the way
empires-server.py sets it up when it runs, with save.db in a temporary folder."""''',
'''"""Tests through the server's real save game layer: flask-session with SQLAlchemy and msgspec, the way
empires-server.py sets it up when it runs (configure_app, the `server` fixture of conftest.py), with save.db in a
temporary folder."""''')
rep('''GATEWAY = "/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php"
''', '''# The client posts its batches to app_url + "flashservices/gateway.php": the Flash player's app_url is the folder of
# ZGame.109338.swf (/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1), Ruffle's the absolute /127.0.0.1
GATEWAY = "/files/empire-s.assets.zgncdn.com/assets/109338/127.0.0.1flashservices/gateway.php"
RUFFLE_GATEWAY = "/127.0.0.1flashservices/gateway.php"
''')
rep('''@pytest.fixture(scope="module")
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


''', '''@pytest.fixture(params=[GATEWAY, RUFFLE_GATEWAY], ids=["flash", "ruffle"])
def gateway(request):
    return request.param


''')
rep('''def batch(client, *calls):
    """Sends calls [(functionName, params), ...] like the client does, returns the answers to the calls."""
    envelope = remoting.Envelope(3)
    body = [{"flashRevision": None}, [{"transaction": None, "sequence": i + 1, "stamp": 0, "params": params,
                                       "functionName": name} for i, (name, params) in enumerate(calls)], 0]
    envelope.bodies = [("/1", remoting.Request("BaseService.dispatchBatch", body=body, envelope=envelope))]
    response = client.post(GATEWAY, data=remoting.encode(envelope).getvalue(), content_type="application/x-amf")''',
'''def batch(client, *calls, gateway=GATEWAY):
    """Sends calls [(functionName, params), ...] like the client does, returns the answers to the calls."""
    envelope = remoting.Envelope(3)
    body = [{"flashRevision": None}, [{"transaction": None, "sequence": i + 1, "stamp": 0, "params": params,
                                       "functionName": name} for i, (name, params) in enumerate(calls)], 0]
    envelope.bodies = [("/1", remoting.Request("BaseService.dispatchBatch", body=body, envelope=envelope))]
    response = client.post(gateway, data=remoting.encode(envelope).getvalue(), content_type="application/x-amf")''')
rep('''def test_a_failing_call_is_undone_and_the_other_calls_are_kept(server, monkeypatch):''',
'''def test_a_failing_call_is_undone_and_the_other_calls_are_kept(server, monkeypatch, gateway):''')
rep('''    answers = batch(client, ("WorldService.addFleet", [fleet("first")]), ("WorldService.addFleet", [fleet("bad")]),
                    ("WorldService.addFleet", [fleet("last")]))

    assert [answer["errorType"] for answer in answers] == [0, empires_server.CALL_FAILED, 0]
    assert answers[1]["errorData"] == "WorldService.addFleet"
''', '''    answers = batch(client, ("WorldService.addFleet", [fleet("first")]), ("WorldService.addFleet", [fleet("bad")]),
                    ("WorldService.addFleet", [fleet("last")]), gateway=gateway)

    assert [answer["errorType"] for answer in answers] == [0, empires_server.CALL_FAILED, 0]
    assert answers[1]["errorData"] == "WorldService.addFleet"
    # the failed call's answer has the fields of every answer (those of the calls that worked), with no data
    assert set(answers[1]) == set(answers[0]) and answers[1]["data"] is None
''')
rep('''def test_overlapping_requests_of_one_save_wait_for_each_other(server, monkeypatch):
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
    try:
        assert slow_started.wait(10)
        fast.start()
        assert not fast_done.wait(0.5)  # the save is in use by the slow request
    finally:  # no request may outlive the test, also when it fails
        go_on.set()
        slow.join(10)
        if fast.ident is not None:  # started
            fast.join(10)

    assert fast_done.is_set()
    assert set(stored(server, sid)["fleets"]) == {"slow", "fast"}  # without waiting, slow writes over fast's fleet
''', '''class WatchedLock:
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
''')
rep('''def test_a_call_that_leaves_an_unsaveable_value_is_undone(server, monkeypatch):''',
'''def test_a_call_that_leaves_an_unsaveable_value_is_undone(server, monkeypatch, gateway):''')
rep('''    answers = batch(client, ("WorldService.addFleet", [fleet("bad")]), ("WorldService.addFleet", [fleet("good")]))
''', '''    answers = batch(client, ("WorldService.addFleet", [fleet("bad")]), ("WorldService.addFleet", [fleet("good")]),
                    gateway=gateway)
''')
rep('''def test_other_saves_changed_by_a_call_that_works_are_written(server, monkeypatch):''',
'''def test_other_saves_changed_by_a_call_that_works_are_written(server, monkeypatch, gateway):''')
rep('''    answers = batch(client, ("WorldService.addFleet", [fleet("first")]))

    assert [answer["errorType"] for answer in answers] == [0]''', '''    answers = batch(client, ("WorldService.addFleet", [fleet("first")]), gateway=gateway)

    assert [answer["errorType"] for answer in answers] == [0]''')
open(p, "wb").write(t.replace("\n", "\r\n").encode("utf-8"))
print("ok")
