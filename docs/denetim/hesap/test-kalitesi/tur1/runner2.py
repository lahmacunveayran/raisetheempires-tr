"""runner.py for the worktree mut2: before each mutation the repo's current test/ folder is copied in (the new tests
and conftest.py), then the mutation is applied. MUT_TESTS (space separated pytest node ids) runs only those tests,
without -x, and records which of them failed; without it the whole suite runs with -x as in runner.py."""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.join(HERE, os.environ.get("MUT_WT", "mut2"))
REPO = r"C:\Users\<user>\Desktop\Raise\raisetheempires-pr"
PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
sys.path.insert(0, HERE)
import runner  # noqa  (apply, nth_index)
from mutations import M  # noqa

runner.WT = WT
RESULTS = os.path.join(HERE, os.environ.get("MUT_RESULTS", "results2.jsonl"))
NOOP = r"C:\Program Files\Git\usr\bin\true.exe"
ENV = dict(os.environ, VISUAL=NOOP, EDITOR=NOOP)
TESTS = os.environ.get("MUT_TESTS", "").split()


def reset():
    subprocess.run(["git", "checkout", "--", "."], cwd=WT, check=True, capture_output=True)
    src, dst = os.path.join(REPO, "test"), os.path.join(WT, "test")
    for name in os.listdir(src):
        if name != "__pycache__" and os.path.isfile(os.path.join(src, name)):
            shutil.copyfile(os.path.join(src, name), os.path.join(dst, name))


def main(ids):
    for mid, path, old, new, desc, occ in M:
        if ids and mid not in ids:
            continue
        reset()
        edits = old if isinstance(old, list) else [(old, new, occ)]
        try:
            line = runner.apply(path, edits)
        except ValueError as e:
            rec = {"id": mid, "status": "NOT_APPLIED", "error": str(e)}
            print(rec, flush=True)
            open(RESULTS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
            continue
        t = time.time()
        args = ([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-W", "ignore", "-o", "faulthandler_timeout=60"]
                + (TESTS if TESTS else ["-x"]))
        p = subprocess.Popen(args, cwd=WT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
        try:
            out, _ = p.communicate(timeout=300 if not TESTS else 150)
            status = "SURVIVED" if p.returncode == 0 else "KILLED"
            failed = [l for l in out.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")]
            summary = [l for l in out.splitlines() if " passed" in l or " failed" in l or " error" in l][-1:]
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            out, _ = p.communicate()
            status, failed, summary = "KILLED", ["TIMEOUT (hang)"], []
        rec = {"id": mid, "file": path, "line": line, "desc": desc, "status": status, "failed": failed,
               "summary": summary, "secs": round(time.time() - t), "tests": TESTS}
        print(rec, flush=True)
        open(RESULTS, "a", encoding="utf-8").write(json.dumps(rec) + "\n")
        if os.environ.get("MUT_KEEP_OUTPUT"):
            open(os.path.join(HERE, "out_%s.txt" % mid), "w", encoding="utf-8").write(out)
    reset()


if __name__ == "__main__":
    main(sys.argv[1:])
