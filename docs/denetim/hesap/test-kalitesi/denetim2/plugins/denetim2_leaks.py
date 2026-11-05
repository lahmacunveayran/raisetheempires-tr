"""pytest plugin (denetim2): after every test, reports threads that are still alive and files that appeared in
the repository folder, to find leaked threads and writes outside temporary folders."""
import os
import threading

_before = None
_report = []


def _snapshot(root):
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "assets", "docs", "turkce", "savespack")]
        for f in filenames:
            p = os.path.join(dirpath, f)
            try:
                out.add((p, os.path.getmtime(p)))
            except OSError:
                pass
    return out


def pytest_sessionstart(session):
    global _before
    _before = _snapshot(str(session.config.rootpath))


def pytest_runtest_teardown(item, nextitem):
    alive = [t for t in threading.enumerate() if t is not threading.main_thread()]
    if alive:
        _report.append((item.nodeid, [(t.name, t.daemon) for t in alive]))


def pytest_sessionfinish(session, exitstatus):
    after = _snapshot(str(session.config.rootpath))
    changed = sorted(p for p, m in after - _before)
    path = os.environ.get("DENETIM2_REPORT", "denetim2_leaks.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("files created or changed in the repository folder during the run:\n")
        for p in changed:
            f.write("  " + p + "\n")
        f.write("tests after which other threads were alive:\n")
        seen = set()
        for nodeid, threads in _report:
            key = tuple(threads)
            f.write("  %s: %s\n" % (nodeid, threads) if key not in seen else "")
            seen.add(key)


# network: every socket connect / bind made during the run is recorded
import socket as _socket
_net = []
_orig_connect = _socket.socket.connect
_orig_bind = _socket.socket.bind


def _connect(self, address):
    _net.append(("connect", repr(address)))
    return _orig_connect(self, address)


def _bind(self, address):
    _net.append(("bind", repr(address)))
    return _orig_bind(self, address)


_socket.socket.connect = _connect
_socket.socket.bind = _bind


def pytest_unconfigure(config):
    path = os.environ.get("DENETIM2_REPORT", "denetim2_leaks.txt")
    with open(path, "a", encoding="utf-8") as f:
        f.write("network calls (socket connect/bind): %d\n" % len(_net))
        for n in sorted(set(_net)):
            f.write("  %s %s\n" % n)
