"""Re-applies the audit's in-scope empires-server.py survivors (denetim2/mut_server_save.json, by their line text) and
a few own mutants to this worktree, one at a time, runs the server tests with a timeout and restores the file.
Usage: python mutants.py [--only id,id] [--out file.json]"""
import argparse
import json
import os
import subprocess
import sys
import time

W = r"C:\Users\<user>\Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-a56ad9a6a592f23b3"
S = r"<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad"
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(S, r"fix2\sunucu\run_pytest_sunucu.py")
TESTS = ["test/server_setup_test.py", "test/session_layer_test.py", "test/empires_test.py"]
AUDIT_IDS = [1, 2, 4, 6, 7, 8, 44, 52, 55, 60, 61, 65, 68, 93, 98, 109, 113, 118, 299, 301, 350, 351, 352, 357]

audit = json.load(open(os.path.join(S, r"denetim2\mut_server_save.json"), encoding="utf-8"))["results"]
MUTANTS = []
for i in AUDIT_IDS:
    r = audit[str(i)]
    if i in (301, 352):  # the decorator line is removed
        MUTANTS.append(("audit#%d" % i, "empires-server.py", r["original"] + "\r\n", "", "line %d: %s removed" % (r["line"], r["original"])))
    elif i == 350:  # the text is also the end of dummy_response's line: take it with its indentation
        MUTANTS.append(("audit#%d" % i, "empires-server.py", "\n            " + r["original"],
                        "\n            " + r["mutant"], "line %d: %s" % (r["line"], r["mutant"])))
    else:
        MUTANTS.append(("audit#%d" % i, "empires-server.py", r["original"], r["mutant"], "line %d: %s" % (r["line"], r["mutant"])))
OWN = [
    ("S1b", "empires-server.py", "            lock.acquire()\r\n            g.save_lock = lock", "            g.save_lock = None",
     "save lock removed cleanly (no acquire, no release)"),
    ("setup-no-host-middleware", "empires-server.py",
     "    app.wsgi_app = KnownHostsOnly(app.wsgi_app)  # around Flask-SocketIO's middleware, so Socket.IO is checked too\r\n    db.init_app",
     "    db.init_app", "configure_app without KnownHostsOnly"),
    ("setup-host-middleware-inside-socketio", "empires-server.py",
     "    socketio.init_app(app)\r\n    app.wsgi_app = KnownHostsOnly(app.wsgi_app)  # around Flask-SocketIO's middleware, so Socket.IO is checked too\r\n",
     "    app.wsgi_app = KnownHostsOnly(app.wsgi_app)\r\n    socketio.init_app(app)\r\n",
     "KnownHostsOnly put inside the Socket.IO middleware"),
    ("setup-no-save-lock", "empires-server.py",
     "    app.session_interface = AssetSkippingSessionInterface(app.session_interface)\r\n    with app.app_context():",
     "    with app.app_context():", "configure_app without AssetSkippingSessionInterface"),
    ("asset-gateway-exception", "empires-server.py",
     'return path.startswith(ASSET_PATH_PREFIXES) and not path.endswith("gateway.php")',
     "return path.startswith(ASSET_PATH_PREFIXES)", "is_asset without the Ruffle gateway exception"),
]
MUTANTS += OWN


def run(timeout):
    env = dict(os.environ, PYTHONPATH=W, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    cmd = [PY, LAUNCHER, "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + TESTS
    t = time.time()
    p = subprocess.Popen(cmd, cwd=W, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        p.communicate()
        return "timeout", time.time() - t, ""
    text = out.decode("utf-8", "replace")
    failed = [line for line in text.splitlines() if line.startswith(("FAILED test", "ERROR test"))]
    return p.returncode, time.time() - t, (failed[0] if failed else text[-300:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=os.path.join(S, r"fix2\sunucu\mutants_result.json"))
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    rc, base, text = run(600)
    assert rc == 0, text
    timeout = 10 * base
    print("baseline", round(base, 1), "s, timeout", round(timeout), flush=True)
    results = {}
    for mid, name, old, new, desc in MUTANTS:
        if only and mid not in only:
            continue
        path = os.path.join(W, name)
        original = open(path, "rb").read()
        text = original.decode("utf-8")
        if text.count(old) != 1:
            results[mid] = {"desc": desc, "status": "NOT APPLIED (%d matches)" % text.count(old)}
            print(mid, results[mid]["status"], flush=True)
            continue
        open(path, "wb").write(text.replace(old, new).encode("utf-8"))
        try:
            rc, t, detail = run(timeout)
        finally:
            open(path, "wb").write(original)
        status = "survived" if rc == 0 else "killed" if rc in (1, 2, 3, 4) else "timeout(killed)" if rc == "timeout" else "error(%s)" % rc
        results[mid] = {"desc": desc, "status": status, "seconds": round(t, 1), "detail": detail}
        print(mid, status, round(t, 1), detail[:160], flush=True)
    json.dump(results, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    st = [r["status"] for r in results.values()]
    print({s: st.count(s) for s in set(st)})


if __name__ == "__main__":
    main()
