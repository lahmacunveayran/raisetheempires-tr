import os
os.remove("log.txt") if os.path.exists("log.txt") else None
for p in ("test/conftest.py", "test/server_setup_test.py"):
    t = open(p, "rb").read().replace(b"\r\n", b"\n")
    open(p, "wb").write(t.replace(b"\n", b"\r\n"))
    print(p, t.count(b"\n"))
