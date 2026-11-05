"""CEK: do_state_rewards/do_costs int() ile okuduğu alanlarda oyun verisinde çözülemeyecek değer var mı?
Durum makinesi değerleri ${ad} yer tutucusu taşıyabilir; bunlar item'in define değerleriyle değiştirilir.
Her item için gerçek değiştirmeyi (game_settings.lookup_state_machine) çalıştırıp sonucu dener."""
import os, sys, collections, io, contextlib
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortam import kur, sessiz
srv, app, tmp = kur(savespack=False)
gs = srv.game_settings
INT = ["-xp", "-energy", "-cash", "-socialXpGood", "-socialXpBad", "-coins", "-buildable", "-upgrade"]
SPLIT = ["-oil", "-wood", "-rare", "-nrare0", "-nrare1", "-nrare2", "-nrare3", "-nrare4", "-aluminum", "-copper", "-gold",
         "-iron", "-uranium"]
bad = collections.Counter()
ornek = {}
n_items = 0
for it in gs["settings"]["items"]["item"]:
    smv = it.get("stateMachineValues")
    if not isinstance(smv, dict) or "-stateMachineName" not in smv:
        continue
    n_items += 1
    with sessiz():
        try:
            sm = srv.lookup_state_machine(smv["-stateMachineName"], smv.get("define", []))
        except Exception as e:
            bad["lookup_state_machine hata"] += 1
            ornek.setdefault("lookup_state_machine hata", []).append((it.get("-name"), smv["-stateMachineName"], type(e).__name__, str(e)[:60]))
            continue
    for s in (sm["state"] if isinstance(sm["state"], list) else [sm["state"]]):
        for f in INT + SPLIT:
            if f in s:
                v = str(s[f])
                try:
                    int(v) if f in INT else int(v.split("|")[0])
                except Exception:
                    bad[f] += 1
                    ornek.setdefault(f, (it.get("-name"), smv["-stateMachineName"], s["-stateName"], v))
print("durum makineli item:", n_items)
print("çözülemeyen alanlar:", dict(bad))
for k, v in ornek.items():
    print("  örnek", k, v)
