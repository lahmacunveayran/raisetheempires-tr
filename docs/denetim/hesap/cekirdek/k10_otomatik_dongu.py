"""CEK: state_machine.click_next_state'teki autoNext döngüsü yalnızca kendine dönen durumu (A->A) durdurur.
Oyun verisindeki durum makinelerinde autoNext zincirlerini tarar: (1) hepsi 0 süreli bir döngü sonsuz döngü olur;
(2) süreli döngüler lastUpdated'dan bu yana geçen süre kadar tur atar (her turda ödül)."""
import json, os, re
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
gs = json.load(open(os.path.join(REPO, "gamesettings-converted.json"), encoding="utf-8"))
sms = gs["settings"]["stateMachines"]["stateMachine"]


def dur(s):
    s = str(s or "0")
    if s.startswith("rand:") or s.startswith("$"):
        return None  # değişkene bağlı
    m = re.fullmatch(r"([\d.]+)(ms|s|m|h|d)?", s)
    if not m:
        return None
    return float(m.group(1)) * {"ms": .001, "s": 1, "m": 60, "h": 3600, "d": 86400, None: 1}[m.group(2)]


sifir, sureli, degisken = [], [], []
for sm in sms:
    states = sm["state"] if isinstance(sm["state"], list) else [sm["state"]]
    by = {s["-stateName"]: s for s in states}
    for start in by:
        seen, cur = [], start
        while cur in by and "-autoNext" in by[cur] and by[cur]["-autoNext"] != cur and cur not in seen:
            seen.append(cur)
            cur = by[cur]["-autoNext"]
        if cur in seen and cur == start:
            ds = [dur(by[s].get("-duration")) for s in seen]
            kayit = (sm["-name"], seen, [by[s].get("-duration", "0") for s in seen])
            if None in ds:
                degisken.append(kayit)
            elif sum(ds) == 0:
                sifir.append(kayit)
            else:
                sureli.append(kayit)
print("durum makinesi:", len(sms))
print("0 süreli autoNext döngüsü:", len(sifir), sifir[:5])
print("süreli autoNext döngüsü:", len(sureli), [(n, c, d) for n, c, d in sureli[:8]])
print("süresi değişkene bağlı döngü:", len(degisken), degisken[:5])
