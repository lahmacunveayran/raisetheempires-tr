import editor
editor.edit = lambda **kwargs: None
import init_settings
init_settings.crash_log = False
init_settings.caching = False
server = __import__("empires-server")
r = server.app.test_client().post("/127.0.0.1flashservices/gateway.php", data=b"x", content_type="application/x-amf")
print(r.status_code, r.mimetype, r.data)
