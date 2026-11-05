import sys
for p in sys.argv[1:]:
    d = open(p, "rb").read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    open(p, "wb").write(d)
    print("crlf", p)
