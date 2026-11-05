"""splice.py FILE MARKER TAILFILE: replace FILE from the line starting with MARKER to its end by TAILFILE."""
import sys
path, marker, tail = sys.argv[1:4]
data = open(path, "rb").read().decode("utf-8")
at = data.index("\n" + marker) + 1
new = data[:at] + open(tail, "rb").read().decode("utf-8")
open(path, "wb").write(new.encode("utf-8"))
print("spliced", path, len(data), "->", len(new))
