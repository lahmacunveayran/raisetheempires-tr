"""CEK: oyun dışı bir istek (sayfa, 404, kayıt düzenleyici) oyunla aynı anda çalışırsa oyunun kaydettiği ilerlemeyi
eski hâliyle ezer.

flask-session her istekte kaydı baştan okur ve (SESSION_PERMANENT + SESSION_REFRESH_EACH_REQUEST varsayılanı yüzünden)
değişmemiş olsa bile sonunda bütün kaydı geri yazar. Kilit yoktur; sunucu threaded=True çalışır.
Sıra elle kuruluyor: A açılır -> B (oyun) kaydeder -> A kapanır.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flask
from ortam import kur, gateway, kayit, yaz, sessiz

srv, app, tmp = kur(savespack=False)
c = app.test_client()
gateway(c, [("UserService.initUser", ["", 0])])
sid = c.get_cookie("session").value
yaz("SESSION_REFRESH_EACH_REQUEST =", app.config["SESSION_REFRESH_EACH_REQUEST"], "| oturum kalıcı mı (SESSION_PERMANENT):", app.session_interface.permanent)

for yol in ("/home.html", "/files/empire-s.assets.zgncdn.com/assets/109338/olmayan.swf", "/save-editor"):
    yaz("is_asset(%r) = %s" % (yol, srv.AssetSkippingSessionInterface.is_asset(yol)))

# A: sayfa isteği başlar (kayıt okunur)
ctx = app.test_request_context("/files/empire-s.assets.zgncdn.com/assets/109338/olmayan.swf",
                               headers={"Cookie": "session=" + sid})
with sessiz():
    ctx.push()
yaz("A açıldı, A'nın gördüğü dünya adı:", flask.session["user_object"]["userInfo"]["worldName"])
# B: oyun bu sırada dünya adını değiştirir ve kaydeder
r, body = gateway(c, [("UserService.setWorldName", ["Oyuncunun yeni adi"])])
yaz("B (setWorldName) ->", r.status_code, "| kayıttaki ad:", kayit(app, sid)["user_object"]["userInfo"]["worldName"])
# A biter: Flask'ın yaptığı gibi save_session
with sessiz():
    resp = app.make_response(("404", 404))
    app.session_interface.save_session(app, flask.session, resp)
    ctx.pop()
yaz("A bitti (hiçbir şey değiştirmedi) -> kayıttaki ad:", kayit(app, sid)["user_object"]["userInfo"]["worldName"])

import flask_socketio, inspect
src = inspect.getsource(flask_socketio.SocketIO.run)
yaz("flask_socketio.run threaded=True:", "threaded=True" in src, "| async_mode:", srv.socketio.async_mode if hasattr(srv.socketio, "async_mode") else "?")
