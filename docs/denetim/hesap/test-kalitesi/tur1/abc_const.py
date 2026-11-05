"""Prints the default values of class constants (abc.py drops them). Usage: abc_const.py <swf> <Class>"""
import os, sys
ARACLAR = r"C:\Users\<user>\Desktop\Raise\raisetheempires-pr\turkce\araclar"
sys.path.insert(0, ARACLAR)
src = open(os.path.join(ARACLAR, "abc.py"), encoding="utf-8").read()
old = """                vi = r.u30()
                if vi:
                    r.u8()"""
new = """                vi = r.u30()
                if vi:
                    t["vk"] = r.u8(); t["vi"] = vi"""
assert old in src
src = src.replace(old, new).replace('if __name__ == "__main__":', 'if False:')
ns = {"__name__": "x"}
exec(compile(src, "abc.py", "exec"), ns)
swf, cls = sys.argv[1:3]
for a in ns["load"](swf):
    for i, inst in enumerate(a.instances):
        if inst["name"] == cls:
            for t in inst["traits"] + a.classes[i]["traits"]:
                if "vi" in t:
                    vk, vi = t["vk"], t["vi"]
                    v = {0x03: a.ints, 0x04: a.uints, 0x06: a.doubles, 0x01: a.strings}.get(vk)
                    print(t["name"], hex(vk), v[vi] if v else vi)
