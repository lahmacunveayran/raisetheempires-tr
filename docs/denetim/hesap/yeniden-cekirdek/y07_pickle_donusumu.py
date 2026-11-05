"""Yeniden denetim: convert_pickled_saves savespack'teki (pickle) kayıtları kayıpsız msgpack'e çeviriyor mu?
Çevirmeden önce pickle.loads ile okunan her kayıt, çevirdikten sonra sunucunun serializer'ıyla okunanla aynı mı.
Çalıştırma: PYTHONIOENCODING=utf-8 ../../../../../venv312/Scripts/python.exe y07_pickle_donusumu.py
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cekirdek"))
from ortam import kur, yaz, sessiz

srv, app, tmp = kur()
with app.app_context():
    si = app.session_interface
    once = {r.session_id: bytes(r.data) for r in si.sql_session_model.query.all()}
    pickle_olan = {k: pickle.loads(v) for k, v in once.items() if v.startswith(b"\x80")}
    with sessiz():
        srv.convert_pickled_saves()
    si.client.session.expire_all()
    sonra = {r.session_id: bytes(r.data) for r in si.sql_session_model.query.all()}
    ayni = sum(1 for k, v in pickle_olan.items() if si.serializer.decode(sonra[k]) == v)
    farkli = [k for k, v in pickle_olan.items() if si.serializer.decode(sonra[k]) != v]
    yaz("kayıt: %d | pickle olan: %d | çevrildikten sonra hâlâ pickle: %d | içerik aynı: %d | farklı: %s" % (
        len(once), len(pickle_olan), sum(1 for v in sonra.values() if v.startswith(b"\x80")), ayni, farkli))
    with sessiz():
        srv.convert_pickled_saves()  # ikinci çalıştırma bir şey yapmamalı
    yaz("ikinci çalıştırmada değişen kayıt:", sum(1 for r in si.sql_session_model.query.all()
                                                 if bytes(r.data) != sonra[r.session_id]))
