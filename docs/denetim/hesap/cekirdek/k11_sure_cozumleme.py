"""CEK: state_machine.parse_duration oyun verisindeki her '-duration' değerini çözebiliyor mu?
(define ile değiştirilen ${...} değerler de taranır: item stateMachineValues/define ve referenceValues/define.)"""
import json, os, sys, collections
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
src = open(os.path.join(REPO, "state_machine.py"), encoding="utf-8").read()
ns = {}
exec(src[src.index("def parse_duration"):src.index("def do_state_rewards")], ns)
parse_duration = ns["parse_duration"]
gs = json.load(open(os.path.join(REPO, "gamesettings-converted.json"), encoding="utf-8"))
vals = collections.Counter()
for sm in gs["settings"]["stateMachines"]["stateMachine"]:
    for s in (sm["state"] if isinstance(sm["state"], list) else [sm["state"]]):
        if "-duration" in s:
            vals[s["-duration"]] += 1


def walk(o):
    if isinstance(o, dict):
        if "-name" in o and "-value" in o and "uration" in str(o["-name"]):
            vals[o["-value"]] += 1
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(gs["settings"]["items"])
bad = {}
for v, n in vals.items():
    if str(v).startswith("$"):
        continue
    try:
        parse_duration(str(v))
    except Exception as e:
        bad[v] = (n, type(e).__name__)
print("farklı süre değeri:", len(vals), "| çözülemeyen:", bad)
print("rand: biçimli olanlar:", {v: n for v, n in vals.items() if str(v).startswith("rand")})
