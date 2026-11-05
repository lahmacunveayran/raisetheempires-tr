import pyamf
from pyamf import remoting
for value in (lambda: 1, object(), {1, 2}):
    ev = remoting.Envelope(pyamf.AMF0)
    ev["/1"] = remoting.Response({"data": [value]})
    try:
        remoting.encode(ev, strict=True, logger=True).getvalue()
        print(type(value), "encoded")
    except Exception as e:
        print(type(value), "fails", type(e), e)
try:
    remoting.decode(b"not amf")
    print("decoded")
except Exception as e:
    print("decode fails", type(e), e)
