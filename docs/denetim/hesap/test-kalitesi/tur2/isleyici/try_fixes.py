"""Puts the proposed fixes into empires-server.py, runs the bug tests (copied into test/), restores the file.
Only to check the proposals; nothing is kept. Run from the worktree root: python try_fixes.py <launcher> <bugs_test>"""
import os
import shutil
import subprocess
import sys

PATH = "empires-server.py"
FIXES = [  # (line, old line content without ending, new lines)
    (2709, '    elif item.get("-subtype") == "expansion":', ['    elif item["-type"] == "expansion":']),
    (2742, '    item_inventory[param] -= 1',
     ['    item_inventory[param] -= 1',
      '    session[\'user_object\']["userInfo"]["player"]["energy"] += int(lookup_item_by_code(param).get("energyYield", 0))']),
    (2758, "    player['energy'] += int(player['energyMax']-player['energy'])  # TODO put item in inventory (storable?)",
     ["    refill = int(player['energyMax'] - player['energy'])",
      "    player['energy'] += refill"]),
    (2760, "    player['cash'] -= int(player['energyMax']-player['energy'])", ["    player['cash'] -= refill"]),
    (2782, "    unlock_expansion(param['index'])",
     ["    pay_expansion(param['code'])", "    unlock_expansion(param['index'])"]),
]
PAY = '''

def pay_expansion(code):
    """GMExpansion.buyExpansion -> Player.buyItem: ExpansionItem.getAmount(cost, scalar) = cost * scalar^n,
    n = expansions.numBitsSet() - len(startingExpansionIndexes), before the new bit is set."""
    item = lookup_item_by_code(code)
    settings = game_settings['settings']['gamesettings']
    player = session['user_object']["userInfo"]["player"]
    n = sum(bin(word).count("1") for word in player["expansions"]["data"]) - \\
        len(settings['-startingExpansionIndexes'].split(","))
    resource_scalar = float(settings['-expansionResourceScalar']) ** n
    do_costs({k: str(int(int(v) * resource_scalar)) for k, v in (item.get("cost") or {}).items()})
    inventory = player["inventory"]["items"]
    for key, v in (item.get("itemcost") or {}).items():
        inventory[key[1:]] = inventory.get(key[1:], 0) - int(int(v) * float(settings['-expansionItemScalar']) ** n)
'''


def main(launcher, bugs):
    original = open(PATH, "rb").read()
    ending = b"\r\n" if b"\r\n" in original else b"\n"
    lines = original.split(ending)
    for line, old, new in sorted(FIXES, reverse=True):
        assert lines[line - 1].decode() == old, (line, lines[line - 1])
        lines[line - 1:line] = [n.encode() for n in new]
    patched = ending.join(lines) + ending.join(PAY.encode().split(b"\n"))
    target = os.path.join("test", os.path.basename(bugs))
    try:
        open(PATH, "wb").write(patched)
        shutil.copy(bugs, target)
        env = dict(os.environ, PYTHONPATH=os.getcwd(), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        out = subprocess.run([sys.executable, launcher, "-q", "-p", "no:cacheprovider", target,
                              "test/server_handlers_test.py"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", env=env, timeout=300)
        print("\n".join(l for l in out.stdout.splitlines() if l.startswith(("FAILED", "E  ")) or " passed" in l
                        or " failed" in l))
    finally:
        open(PATH, "wb").write(original)
        os.remove(target)
    assert open(PATH, "rb").read() == original


if __name__ == "__main__":
    main(*sys.argv[1:])
