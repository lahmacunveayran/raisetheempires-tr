"""CEK: istemciden gelen ve msgspec'in kodlayamadığı bir değer (AMF 'undefined' -> pyamf.Undefined) oturuma
yazılırsa kayıt hiç saklanamaz; istek HTTP 200 'It went wrong' ile biter, paketteki her şey kaybolur.

transactional_session yalnızca görünüm içindeki hatayı yakalar; save_session'daki kodlama hatası onun dışındadır.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pyamf
from ortam import kur, gateway, kayit, yaz, hatalar

srv, app, tmp = kur(savespack=False)
c = app.test_client()
gateway(c, [("UserService.initUser", ["", 0])])
sid = c.get_cookie("session").value

r, body = gateway(c, [("UserService.setWorldName", ["Yeni ad"]),
                      ("UserService.saveOptions", [{"musicDisabled": True, "sfxDisabled": pyamf.Undefined}])])
yaz("setWorldName + saveOptions(undefined alanlı) -> HTTP", r.status_code, r.content_type, "|", body)
yaz("kayıttaki ad:", kayit(app, sid)["user_object"]["userInfo"]["worldName"])
for h in hatalar(tmp)[-3:]:
    yaz("  log.txt:", h)
r, body = gateway(c, [("UserService.setWorldName", ["Yeni ad"])])
yaz("aynı ad tek başına -> HTTP", r.status_code, "| kayıttaki ad:", kayit(app, sid)["user_object"]["userInfo"]["worldName"])
