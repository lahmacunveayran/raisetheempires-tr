"""Istemcideki bir metodun imzasini (parametre ve donus tipleri) yazar.
Kullanim (depo kokunden): python docs/denetim/hesap/savas/abc_imza.py <swf> <Sinif> <metod>
turkce/araclar/abc.py donus tipini atliyor; burada ayni kodu, donus tipini saklayacak bicimde yamayip calistiriyoruz.
Depodaki abc.py degistirilmez."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
ARACLAR = os.path.join(ROOT, "turkce", "araclar")
sys.path.insert(0, ARACLAR)
with open(os.path.join(ARACLAR, "abc.py"), encoding="utf-8") as f:
    src = f.read()
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
                                    'self.methods.append({"name": self.strings[name], "params": pc, "ret": ret, "ptypes": ptypes})')
src = src.replace('if __name__ == "__main__":', 'if False:')
ns = {"__name__": "rte_abc"}
exec(compile(src, "abc.py", "exec"), ns)

swf, cls, meth = sys.argv[1:4]
for a in ns["load"](swf):
    for m, (c, n) in a.owner.items():
        if c == cls and n == meth:
            info = a.methods[m]
            print("%s.%s(%s) : %s" % (c, n, ", ".join(a.mname(p) for p in info["ptypes"]), a.mname(info["ret"])))
