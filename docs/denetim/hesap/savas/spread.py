"""bot_empires.SPREAD yorumunu dogrular: "with 0.5 about one defender in 60 is more than 1.5 times off, one in 8 with 0".
Rastgele takimlar (testtekiyle ayni cekim) icin her savunanin gucunun kendi hedefine (oyuncu birimi x seviye carpani)
oranina bakar. Kullanim (depo kokunden): python docs/denetim/hesap/savas/spread.py"""
import itertools, math, os, random, sys
sys.argv = sys.argv[:1]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_denge as B
from flask import session
be = B.bot_empires

def off_rate(spread, n_squads=300):
    be.SPREAD = spread
    rng = random.Random(3)
    off = total = 0
    with B.T.app.test_request_context():
        session.sid = "0"
        for _ in range(n_squads):
            level = rng.randrange(10, 100, 5)
            pool = [i["-code"] for i in be.DEFENDER_POOL if level - 20 <= int(i["requiredLevel"]) <= level]
            units = [rng.choice(pool) for _ in range(rng.randint(3, 5))]
            B.setup(level, units)
            squad = be.player_squad()
            for bot in be.bots():
                # bot_empires.defense_fleet'in ilk satirlari aynen: yuva (tur, hedef guc) ve secilen gucler
                pool = [i for i in be.DEFENDER_POOL if int(i["requiredLevel"]) <= be.level(bot)]
                factor = be.STRENGTH_PER_LEVEL ** (be.level(bot) - level - be.HANDICAP)
                kinds = sorted({be._kind(i) for i in pool})
                slots = [(min(kinds, key=lambda k: (abs(be._advantage(k, squad) - be._advantage(kind, squad)), k != kind)),
                          st * factor) for kind, st in squad]
                options = [sorted({be._strength(i) for i in pool if be._kind(i) == kind},
                                  key=lambda x: abs(math.log(x / target)))[:be.CHOICES] for kind, target in slots]
                strengths = min(itertools.product(*options), key=lambda ss: be._error(slots, ss))
                for (_, t), g in zip(slots, strengths):
                    total += 1
                    off += max(g / t, t / g) > 1.5
    return off, total

for s in (0.5, 0):
    off, total = off_rate(s)
    print("SPREAD", s, ": 1.5 kattan fazla sapan savunan", off, "/", total, "= 1/%.0f" % (total / off if off else float('inf')))
