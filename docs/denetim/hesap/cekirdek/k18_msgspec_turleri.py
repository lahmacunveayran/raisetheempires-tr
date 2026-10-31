"""CEK-05 kanıtı: pyamf'in ürettiği türlerden hangileri msgspec ile (sunucunun enc_hook'u gibi reddeden bir kancayla)
kodlanabiliyor; pickle baytları msgspec çözücülerinden geçiyor mu."""
import msgspec, pyamf, datetime, pickle
from pyamf import amf3
enc = msgspec.msgpack.Encoder(enc_hook=lambda o: (_ for _ in ()).throw(TypeError(type(o))))
cases = {
 "ASObject": pyamf.ASObject(a=1),
 "TypedObject": pyamf.TypedObject("x.Y"),
 "MixedArray": pyamf.MixedArray({"a": 1}),
 "Undefined": pyamf.Undefined,
 "datetime": datetime.datetime.now(),
 "tuple": (1, 2),
 "ByteArray": amf3.ByteArray(b"ab"),
 "intkey": {1: "a"},
}
for k, v in cases.items():
    try:
        b = enc.encode({"x": v}); print(k, "OK ->", msgspec.msgpack.decode(b))
    except Exception as e:
        print(k, "FAIL", type(e).__name__, e)
# pickled bytes decode via msgspec?
p = pickle.dumps({"user_object": 1}, pickle.HIGHEST_PROTOCOL)
for dec in (msgspec.msgpack.Decoder(), msgspec.json.Decoder()):
    try: print("pickle via", dec, dec.decode(p))
    except Exception as e: print("pickle via", type(dec).__name__, "->", type(e).__name__)
