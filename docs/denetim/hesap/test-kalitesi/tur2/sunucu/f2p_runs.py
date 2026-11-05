"""Fail-to-pass runs that need test files swapped: each case puts the given files in the worktree, runs the suite (or
part), restores the files, and prints the tail. Usage: python f2p_runs.py <case>"""
import os
import shutil
import subprocess
import sys
import time

W = r"C:\Users\<user>\Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-a56ad9a6a592f23b3"
R = r"<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad\fix2\sunucu"
PLUGINS = r"<HOME>\AppData\Local\Temp\claude\44db76dc85e0ce87\6e027af0-22bc-435d-8563-59919183e99e\scratchpad\denetim2\plugins"
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"


def run(args, seed=None, timeout=600):
    env = dict(os.environ, PYTHONPATH=W + ";" + PLUGINS, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if seed:
        env["SHUFFLE_SEED"] = seed
        args = ["-p", "denetim2_shuffle"] + args
    cmd = [PY, os.path.join(R, "run_pytest_sunucu.py"), "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + args
    p = subprocess.run(cmd, cwd=W, env=env, capture_output=True, timeout=timeout)
    text = p.stdout.decode("utf-8", "replace")
    lines = [l for l in text.splitlines() if " passed" in l or " failed" in l or " error" in l or "changed files" in l
             or l.startswith("  ") and not l.startswith("   ")]
    return p.returncode, lines[-12:]


def swapped(files, fn):
    saved = {}
    for name, source in files.items():
        path = os.path.join(W, name)
        saved[name] = open(path, "rb").read()
        if callable(source):
            open(path, "wb").write(source(saved[name]))
        else:
            shutil.copyfile(source, path)
    try:
        return fn()
    finally:
        for name, data in saved.items():
            open(os.path.join(W, name), "wb").write(data)


def clean():
    for leftover in ("log.txt",):
        p = os.path.join(W, leftover)
        if os.path.exists(p):
            os.remove(p)
    shutil.rmtree(os.path.join(W, "cache"), ignore_errors=True)


case = sys.argv[1]
if case == "old-shuffle":  # B-O1 before: the cb00c06 conftest + session_layer_test, shuffled
    for seed in ("11", "22", "33"):
        print(seed, swapped({"test/conftest.py": os.path.join(R, "old_conftest.py"),
                             "test/session_layer_test.py": os.path.join(R, "old_session_layer_test.py")},
                            lambda: run(["test", "--ignore=test/server_setup_test.py"], seed)))
    clean()
elif case == "no-log-redirect":  # B-D1: the conftest without the log redirect
    clean()
    print(swapped({"test/conftest.py": lambda b: b.replace(
        b"daiquiri.output._get_log_file_path = lambda *args:", b"_unused = lambda *args:")},
        lambda: run(["test/battle_test.py"])))
    clean()
elif case == "caching-on":  # B-D1: the conftest without caching off
    clean()
    print(swapped({"test/conftest.py": lambda b: b.replace(b"init_settings.caching = False", b"pass")},
                  lambda: run(["test/battle_test.py"])))
    clean()
elif case == "old-overlap-slow-machine":  # B-D2: the cb00c06 overlap test passes with the lock removed if slow
    pass
