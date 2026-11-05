"""replace_block.py FILE START_MARKER END_MARKER NEWFILE: replace from the line starting with START_MARKER up to
(not including) the line starting with END_MARKER by NEWFILE (plus two blank lines)."""
import sys
path, start, end, new = sys.argv[1:5]
data = open(path, "rb").read().decode("utf-8")
a = data.index("\n" + start) + 1
b = data.index("\n" + end, a) + 1
block = open(new, "rb").read().decode("utf-8").rstrip("\n") + "\n\n\n"
out = data[:a] + block + data[b:]
open(path, "wb").write(out.encode("utf-8"))
print("replaced", len(data[a:b]), "chars by", len(block))
