"""Applies the row-4 fix to <wt>/battle_engine.py, runs the given test, restores the file byte for byte."""
import os
import subprocess
import sys

wt, test = sys.argv[1], sys.argv[2]
path = os.path.join(wt, "battle_engine.py")
original = open(path, "rb").read()
lines = original.split(b"\n")
assert lines[1157].count(b"[0,0,4,3,0]]") == 1
lines[1157] = lines[1157].replace(b"[0,0,4,3,0]]", b"[0,0,3,4,0]]")
try:
    open(path, "wb").write(b"\n".join(lines))
    env = dict(os.environ, PYTHONPATH=wt, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe",
                        os.path.join(here, "run_pytest_odul.py"), "-q", "-p", "no:cacheprovider"] + sys.argv[2:],
                       cwd=wt, env=env, capture_output=True, text=True, timeout=600)
    print(r.stdout[-600:])
finally:
    open(path, "wb").write(original)
    assert open(path, "rb").read() == original
