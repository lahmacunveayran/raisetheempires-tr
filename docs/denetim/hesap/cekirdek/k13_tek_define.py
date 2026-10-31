"""CEK: stateMachineValues/define tek öğe olduğunda (liste değil, sözlük) click_next_state -> lookup_state_machine
TypeError verir. Raffle Center (40.000 altın, satın alınabilir) yerleştirildiği anda paket çöker.
Ayrıca WorldGamesStadiumStateMachine oyun verisinde iki kez tanımlı -> ValueError."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, gateway, kayit, oturumlar, yaz, hatalar

srv, app, tmp = kur()
ben = next(i for i in oturumlar(app) if i.startswith("session:c519d7e7"))[len("session:"):]
c = app.test_client()
c.set_cookie("session", ben)
gateway(c, [("UserService.initUser", ["", 0])])
once = kayit(app, ben)["user_object"]["userInfo"]["world"]
n, altin = len(once["objects"]), once["resources"]["coins"]
for ad in ("Raffle Center", "World_Games_Stadium1"):
    r, body = gateway(c, [("WorldService.performAction", ["place", {"id": 0, "position": "60,60,0", "itemName": ad},
                                                          [{"isGift": False}]])])
    w = kayit(app, ben)["user_object"]["userInfo"]["world"]
    yaz("place %-20s -> HTTP %s %s | nesne sayısı %d->%d, altın %s->%s" % (
        ad, r.status_code, "AMF" if r.content_type == "application/x-amf" else r.data[:15], n, len(w["objects"]),
        altin, w["resources"]["coins"]))
for h in hatalar(tmp)[-2:]:
    yaz("  log.txt:", h)
