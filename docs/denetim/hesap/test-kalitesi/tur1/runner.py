import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.join(HERE, os.environ.get("MUT_WT", "mut"))
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
sys.path.insert(0, HERE)
from mutations import M  # noqa

RESULTS = os.path.join(HERE, os.environ.get("MUT_RESULTS", "results.jsonl"))
EXTRA = []
NOOP = r"C:\Program Files\Git\usr\bin\true.exe"
ENV = dict(os.environ, VISUAL=NOOP, EDITOR=NOOP)
if os.environ.get("MUT_TMP"):
    os.makedirs(os.environ["MUT_TMP"], exist_ok=True)
    ENV.update(TEMP=os.environ["MUT_TMP"], TMP=os.environ["MUT_TMP"])


def reset():
    subprocess.run(["git", "checkout", "--", "."], cwd=WT, check=True, capture_output=True)
    shutil.copyfile(os.path.join(HERE, "conftest.py.keep"), os.path.join(WT, "test", "conftest.py"))


def nth_index(text, old, occ):
    start = -1
    for _ in range(occ + 1):
        start = text.find(old, start + 1)
        if start < 0:
            return -1
    return start


def apply(path, edits):
    full = os.path.join(WT, path)
    with open(full, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    for old, new, occ in edits:
        if crlf:
            old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
        if occ is None:
            if text.count(old) != 1:
                raise ValueError("old string found %d times" % text.count(old))
            i = text.index(old)
        else:
            i = nth_index(text, old, occ)
            if i < 0:
                raise ValueError("occurrence %d not found" % occ)
        line = text[:i].count("\n") + 1
        text = text[:i] + new + text[i + len(old):]
    with open(full, "wb") as f:
        f.write(text.encode("utf-8"))
    return line


def main(ids):
    for mid, path, old, new, desc, occ in M:
        if ids and mid not in ids:
            continue
        reset()
        edits = old if isinstance(old, list) else [(old, new, occ)]
        try:
            line = apply(path, edits)
        except ValueError as e:
            rec = {"id": mid, "file": path, "desc": desc, "status": "NOT_APPLIED", "error": str(e)}
            print(rec, flush=True)
            open(RESULTS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
            continue
        t = time.time()
        p = subprocess.Popen([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-W", "ignore",
                              "-o", "faulthandler_timeout=60"] + EXTRA, cwd=WT, env=ENV,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        try:
            out, _ = p.communicate(timeout=150)
            status = "SURVIVED" if p.returncode == 0 else "KILLED"
            failed = [l for l in out.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")]
            summary = [l for l in out.splitlines() if " passed" in l or " failed" in l or " error" in l][-1:]
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            out, _ = p.communicate()
            status, failed, summary = "KILLED", ["TIMEOUT (hang)"], []
            open(os.path.join(HERE, "hang_%s.txt" % mid), "w", encoding="utf-8").write(out)
        rec = {"id": mid, "file": path, "line": line, "desc": desc, "status": status, "failed": failed,
               "summary": summary, "secs": round(time.time() - t)}
        print(rec, flush=True)
        open(RESULTS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
    reset()


if __name__ == "__main__":
    main(sys.argv[1:])
