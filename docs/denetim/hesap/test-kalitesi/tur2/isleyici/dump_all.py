"""Dumps the disassembly of every method of the client to one text file (uses turkce/araclar/abc.py)."""
import sys
sys.path.insert(0, sys.argv[1])
import abc as _  # noqa  (stdlib abc already loaded; load the tool by path)
import importlib.util
spec = importlib.util.spec_from_file_location("abctool", sys.argv[1] + "/abc.py")
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
with open(sys.argv[3], "w", encoding="utf-8") as out:
    for a in tool.load(sys.argv[2]):
        for m, code in a.bodies.items():
            cls, name = a.owner.get(m, ("?", "m%d" % m))
            out.write("== %s.%s\n" % (cls, name))
            out.write("\n".join(tool.disasm(a, code)) + "\n")
