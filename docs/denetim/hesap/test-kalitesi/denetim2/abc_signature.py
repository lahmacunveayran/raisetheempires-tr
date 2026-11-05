"""Prints the declared return type and parameter types of client methods (turkce/araclar/abc.py reads but drops them).

Loads abc.py's source with the two discarded reads kept, without changing the file.
Usage: python abc_signature.py <repo> Class.method [Class.method ...]
"""
import sys
import types

repo = sys.argv[1]
src = open(repo + r"\turkce\araclar\abc.py", encoding="utf-8").read()
old = """            pc = r.u30()
            r.u30()
            for _ in range(pc):
                r.u30()
            name = r.u30()"""
new = """            pc = r.u30()
            ret = r.u30()
            ptypes = [r.u30() for _ in range(pc)]
            name = r.u30()"""
assert old in src
src = src.replace(old, new).replace('self.methods.append({"name": self.strings[name], "params": pc})',
                                    'self.methods.append({"name": self.strings[name], "params": pc, "ret": ret, '
                                    '"ptypes": ptypes})')
sys.path.insert(0, repo + r"\turkce\araclar")
mod = types.ModuleType("abc_tool")
exec(compile(src.replace("if __name__ == \"__main__\":", "if False:"), "abc_tool", "exec"), mod.__dict__)
wanted = [a.split(".") for a in sys.argv[2:]]
for abc in mod.load(repo + r"\assets\ZGame.109338.swf"):
    for m, (cls, name) in abc.owner.items():
        for c, n in wanted:
            if cls == c and name == n:
                info = abc.methods[m]
                print("%s.%s(%s): %s" % (cls, name, ", ".join(abc.mname(p) for p in info["ptypes"]),
                                         abc.mname(info["ret"]) if info["ret"] else "*"))
