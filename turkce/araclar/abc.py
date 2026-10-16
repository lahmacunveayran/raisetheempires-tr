"""Minimal AVM2 (ActionScript 3) bytecode reader for the game client.

Usage:
  python abc.py <swf> strings <regex>          strings in the constant pool matching regex
  python abc.py <swf> classes <regex>          classes whose name matches, with their traits
  python abc.py <swf> method <Class> <name>    disassemble one method (name '' = constructor)
  python abc.py <swf> refs <regex>             methods whose code references a matching name/string
"""
import re
import struct
import sys

from swf import read_swf


class R:
    def __init__(self, b, p=0):
        self.b, self.p = b, p

    def u8(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.b, self.p)[0]
        self.p += 2
        return v

    def s24(self):
        v = int.from_bytes(self.b[self.p:self.p + 3], "little", signed=True)
        self.p += 3
        return v

    def u30(self):
        v = sh = 0
        while True:
            c = self.u8()
            v |= (c & 0x7F) << sh
            sh += 7
            if not c & 0x80 or sh >= 35:
                return v

    def s32(self):
        v = self.u30()
        return v - (1 << 32) if v & 0x80000000 else v

    def d64(self):
        v = struct.unpack_from("<d", self.b, self.p)[0]
        self.p += 8
        return v

    def bytes(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v


class ABC:
    def __init__(self, data):
        r = R(data, 4)
        self.ints = [0] + [r.s32() for _ in range(r.u30() - 1)] if True else None
        n = r.u30()
        self.uints = [0] + [r.u30() for _ in range(max(n - 1, 0))]
        n = r.u30()
        self.doubles = [0.0] + [r.d64() for _ in range(max(n - 1, 0))]
        n = r.u30()
        self.strings = [""] + [r.bytes(r.u30()).decode("utf-8", "replace") for _ in range(max(n - 1, 0))]
        n = r.u30()
        self.ns = [None]
        for _ in range(max(n - 1, 0)):
            kind = r.u8()
            self.ns.append((kind, self.strings[r.u30()]))
        n = r.u30()
        self.nssets = [None] + [[r.u30() for _ in range(r.u30())] for _ in range(max(n - 1, 0))]
        n = r.u30()
        self.mn = [None]
        for _ in range(max(n - 1, 0)):
            k = r.u8()
            if k in (0x07, 0x0D):
                ns, name = r.u30(), r.u30()
                self.mn.append(("Q", self.strings[name], ns))
            elif k in (0x0F, 0x10):
                self.mn.append(("RTQ", self.strings[r.u30()]))
            elif k in (0x11, 0x12):
                self.mn.append(("RTQL", ""))
            elif k in (0x09, 0x0E):
                name = r.u30()
                r.u30()
                self.mn.append(("M", self.strings[name]))
            elif k in (0x1B, 0x1C):
                r.u30()
                self.mn.append(("ML", ""))
            elif k == 0x1D:
                base = r.u30()
                params = [r.u30() for _ in range(r.u30())]
                self.mn.append(("T", base, params))
            else:
                raise ValueError("multiname kind %x" % k)
        self.methods = []
        for _ in range(r.u30()):
            pc = r.u30()
            r.u30()
            for _ in range(pc):
                r.u30()
            name = r.u30()
            flags = r.u8()
            if flags & 0x08:
                for _ in range(r.u30()):
                    r.u30()
                    r.u8()
            if flags & 0x80:
                for _ in range(pc):
                    r.u30()
            self.methods.append({"name": self.strings[name], "params": pc})
        for _ in range(r.u30()):  # metadata
            r.u30()
            n = r.u30()
            for _ in range(n * 2):
                r.u30()
        nclass = r.u30()
        self.instances = []
        for _ in range(nclass):
            name, sup = r.u30(), r.u30()
            flags = r.u8()
            if flags & 0x08:
                r.u30()
            for _ in range(r.u30()):
                r.u30()
            iinit = r.u30()
            self.instances.append({"name": self.mname(name), "super": self.mname(sup), "iinit": iinit,
                                   "traits": self.traits(r)})
        self.classes = []
        for _ in range(nclass):
            cinit = r.u30()
            self.classes.append({"cinit": cinit, "traits": self.traits(r)})
        for _ in range(r.u30()):  # scripts
            r.u30()
            self.traits(r)
        self.bodies = {}
        for _ in range(r.u30()):
            m = r.u30()
            r.u30(), r.u30(), r.u30(), r.u30()
            code = r.bytes(r.u30())
            exc = [(r.u30(), r.u30(), r.u30(), r.u30(), r.u30()) for _ in range(r.u30())]
            self.traits(r)
            self.bodies[m] = code
        self.owner = {}
        for i, inst in enumerate(self.instances):
            self.owner[inst["iinit"]] = (inst["name"], "<init>")
            self.owner[self.classes[i]["cinit"]] = (inst["name"], "<cinit>")
            for t in inst["traits"] + self.classes[i]["traits"]:
                if "method" in t:
                    self.owner[t["method"]] = (inst["name"], t["name"])

    def mname(self, i):
        m = self.mn[i] if i < len(self.mn) else None
        if m is None:
            return "*"
        if m[0] == "T":
            return "%s.<%s>" % (self.mname(m[1]), ",".join(self.mname(p) for p in m[2]))
        return m[1]

    def traits(self, r):
        out = []
        for _ in range(r.u30()):
            name = self.mname(r.u30())
            kind = r.u8()
            k = kind & 0x0F
            t = {"name": name, "kind": k}
            if k in (0, 6):
                r.u30()
                t["type"] = self.mname(r.u30())
                vi = r.u30()
                if vi:
                    r.u8()
            elif k in (1, 2, 3):
                r.u30()
                t["method"] = r.u30()
                t["kind"] = ("method", "getter", "setter")[k - 1]
            elif k == 4:
                r.u30()
                r.u30()
            elif k == 5:
                r.u30()
                t["method"] = r.u30()
            if kind & 0x40:
                for _ in range(r.u30()):
                    r.u30()
            out.append(t)
        return out


# opcode -> (name, operand kinds)  u=u30 mn s=string i=int d=double b=s24 branch, y=u8
OPS = {
    0x02: ("nop", ""), 0x03: ("throw", ""), 0x04: ("getsuper", "m"), 0x05: ("setsuper", "m"),
    0x08: ("kill", "u"), 0x09: ("label", ""), 0x0C: ("ifnlt", "b"), 0x0D: ("ifnle", "b"), 0x0E: ("ifngt", "b"),
    0x0F: ("ifnge", "b"), 0x10: ("jump", "b"), 0x11: ("iftrue", "b"), 0x12: ("iffalse", "b"), 0x13: ("ifeq", "b"),
    0x14: ("ifne", "b"), 0x15: ("iflt", "b"), 0x16: ("ifle", "b"), 0x17: ("ifgt", "b"), 0x18: ("ifge", "b"),
    0x19: ("ifstricteq", "b"), 0x1A: ("ifstrictne", "b"), 0x1B: ("lookupswitch", "L"), 0x1C: ("pushwith", ""),
    0x1D: ("popscope", ""), 0x1E: ("nextname", ""), 0x1F: ("hasnext", ""), 0x20: ("pushnull", ""),
    0x21: ("pushundefined", ""), 0x23: ("nextvalue", ""), 0x24: ("pushbyte", "y"), 0x25: ("pushshort", "u"),
    0x26: ("pushtrue", ""), 0x27: ("pushfalse", ""), 0x28: ("pushnan", ""), 0x29: ("pop", ""), 0x2A: ("dup", ""),
    0x2B: ("swap", ""), 0x2C: ("pushstring", "s"), 0x2D: ("pushint", "i"), 0x2E: ("pushuint", "u"),
    0x2F: ("pushdouble", "d"), 0x30: ("pushscope", ""), 0x31: ("pushnamespace", "u"), 0x32: ("hasnext2", "uu"),
    0x40: ("newfunction", "u"), 0x41: ("call", "u"), 0x42: ("construct", "u"), 0x43: ("callmethod", "uu"),
    0x44: ("callstatic", "uu"), 0x45: ("callsuper", "mu"), 0x46: ("callproperty", "mu"), 0x47: ("returnvoid", ""),
    0x48: ("returnvalue", ""), 0x49: ("constructsuper", "u"), 0x4A: ("constructprop", "mu"),
    0x4C: ("callproplex", "mu"), 0x4E: ("callsupervoid", "mu"), 0x4F: ("callpropvoid", "mu"),
    0x53: ("applytype", "u"), 0x55: ("newobject", "u"), 0x56: ("newarray", "u"), 0x57: ("newactivation", ""),
    0x58: ("newclass", "u"), 0x59: ("getdescendants", "m"), 0x5A: ("newcatch", "u"), 0x5D: ("findpropstrict", "m"),
    0x5E: ("findproperty", "m"), 0x5F: ("finddef", "m"), 0x60: ("getlex", "m"), 0x61: ("setproperty", "m"),
    0x62: ("getlocal", "u"), 0x63: ("setlocal", "u"), 0x64: ("getglobalscope", ""), 0x65: ("getscopeobject", "y"),
    0x66: ("getproperty", "m"), 0x68: ("initproperty", "m"), 0x6A: ("deleteproperty", "m"), 0x6C: ("getslot", "u"),
    0x6D: ("setslot", "u"), 0x6E: ("getglobalslot", "u"), 0x6F: ("setglobalslot", "u"), 0x70: ("convert_s", ""),
    0x71: ("esc_xelem", ""), 0x72: ("esc_xattr", ""), 0x73: ("convert_i", ""), 0x74: ("convert_u", ""),
    0x75: ("convert_d", ""), 0x76: ("convert_b", ""), 0x77: ("convert_o", ""), 0x78: ("checkfilter", ""),
    0x80: ("coerce", "m"), 0x82: ("coerce_a", ""), 0x85: ("coerce_s", ""), 0x86: ("astype", "m"),
    0x87: ("astypelate", ""), 0x90: ("negate", ""), 0x91: ("increment", ""), 0x92: ("inclocal", "u"),
    0x93: ("decrement", ""), 0x94: ("declocal", "u"), 0x95: ("typeof", ""), 0x96: ("not", ""), 0x97: ("bitnot", ""),
    0xA0: ("add", ""), 0xA1: ("subtract", ""), 0xA2: ("multiply", ""), 0xA3: ("divide", ""), 0xA4: ("modulo", ""),
    0xA5: ("lshift", ""), 0xA6: ("rshift", ""), 0xA7: ("urshift", ""), 0xA8: ("bitand", ""), 0xA9: ("bitor", ""),
    0xAA: ("bitxor", ""), 0xAB: ("equals", ""), 0xAC: ("strictequals", ""), 0xAD: ("lessthan", ""),
    0xAE: ("lessequals", ""), 0xAF: ("greaterthan", ""), 0xB0: ("greaterequals", ""), 0xB1: ("instanceof", ""),
    0xB2: ("istype", "m"), 0xB3: ("istypelate", ""), 0xB4: ("in", ""), 0xC0: ("increment_i", ""),
    0xC1: ("decrement_i", ""), 0xC2: ("inclocal_i", "u"), 0xC3: ("declocal_i", "u"), 0xC4: ("negate_i", ""),
    0xC5: ("add_i", ""), 0xC6: ("subtract_i", ""), 0xC7: ("multiply_i", ""), 0xD0: ("getlocal0", ""),
    0xD1: ("getlocal1", ""), 0xD2: ("getlocal2", ""), 0xD3: ("getlocal3", ""), 0xD4: ("setlocal0", ""),
    0xD5: ("setlocal1", ""), 0xD6: ("setlocal2", ""), 0xD7: ("setlocal3", ""), 0xEF: ("debug", "yuyu"),
    0xF0: ("debugline", "u"), 0xF1: ("debugfile", "u"), 0x6B: ("getouterscope", "u"),
}


def disasm(abc, code):
    r = R(code)
    out = []
    while r.p < len(code):
        at = r.p
        op = r.u8()
        name, args = OPS.get(op, ("op_%02x" % op, ""))
        vals = []
        if args == "L":
            base = at
            vals.append("default->%d" % (base + r.s24()))
            n = r.u30()
            vals += ["%d" % (base + r.s24()) for _ in range(n + 1)]
        else:
            for a in args:
                if a == "u":
                    vals.append(str(r.u30()))
                elif a == "m":
                    vals.append(abc.mname(r.u30()))
                elif a == "s":
                    vals.append(repr(abc.strings[r.u30()]))
                elif a == "i":
                    vals.append(str(abc.ints[r.u30()]))
                elif a == "d":
                    vals.append(str(abc.doubles[r.u30()]))
                elif a == "y":
                    vals.append(str(r.u8()))
                elif a == "b":
                    off = r.s24()
                    vals.append("->%d" % (r.p + off))
        if name in ("debugline", "debugfile", "debug", "label", "nop"):
            continue
        out.append("%5d %s %s" % (at, name, " ".join(vals)))
    return out


def load(path):
    abcs = []
    for code, tag in read_swf(path)["tags"]:
        if code == 82:
            p = 4
            while tag[p]:
                p += 1
            abcs.append(ABC(tag[p + 1:]))
        elif code == 72:
            abcs.append(ABC(tag))
    return abcs


def main(path, cmd, *args):
    for abc in load(path):
        if cmd == "strings":
            rx = re.compile(args[0])
            for s in abc.strings:
                if rx.search(s):
                    print(repr(s))
        elif cmd == "classes":
            rx = re.compile(args[0])
            for i, inst in enumerate(abc.instances):
                if rx.search(inst["name"]):
                    print("class %s extends %s" % (inst["name"], inst["super"]))
                    for t in inst["traits"]:
                        print("   ", t["kind"], t["name"], t.get("type", ""))
                    for t in abc.classes[i]["traits"]:
                        print("    static", t["kind"], t["name"], t.get("type", ""))
        elif cmd == "method":
            for m, (cls, name) in abc.owner.items():
                if cls == args[0] and name == (args[1] or "<init>") and m in abc.bodies:
                    print("== %s.%s" % (cls, name))
                    print("\n".join(disasm(abc, abc.bodies[m])))
        elif cmd == "refs":
            rx = re.compile(args[0])
            for m, code in abc.bodies.items():
                text = "\n".join(disasm(abc, code))
                if rx.search(text):
                    print("%s.%s" % abc.owner.get(m, ("?", "m%d" % m)))


if __name__ == "__main__":
    main(*sys.argv[1:])
