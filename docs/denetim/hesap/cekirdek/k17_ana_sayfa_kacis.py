"""CEK: home.html'de allies listesi `{{ allies | safe }}` ile <script> içine basılır; json.dumps '</script>'i kaçırmaz.
Bir yerel kaydın dünya adı (UserService.setWorldName ile istemciden gelir) başka kaydın ana sayfasındaki betiği kırar."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, oturumlar, yaz, sessiz

srv, app, tmp = kur()
ids = [i[len("session:"):] for i in oturumlar(app)]
a = app.test_client(); a.set_cookie("session", next(i for i in ids if i.startswith("623fecce")))
gateway(a, [("UserService.initUser", ["", 0]), ("UserService.setWorldName", ["</script><b id=enjekte>x</b><script>"])])
b = app.test_client(); b.set_cookie("session", next(i for i in ids if i.startswith("c519d7e7")))
with sessiz():
    html = b.get("/home.html").get_data(as_text=True)
yaz("diğer kaydın home.html'inde kaçışsız '</script><b id=enjekte>' var mı:", "</script><b id=enjekte>" in html)
