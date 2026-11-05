"""NOT in the committed suite: shows a server difference from the client (battle_engine.py is not odul's file).

ChipDamageManager.uniqueNumber, 5 live units, target index 4 (bytecode offsets 378-401): other index 3 -> 4,
other index 2 -> 3, else 0, so its row is [0, 0, 3, 4, 0]. battle_engine.get_adjacent_factor (line 1158) has
[0, 0, 4, 3, 0]: a flak barrage on the fifth of five enemies hits the third for 4 and the fourth for 3, the client
the third for 3 and the fourth for 4 (and stops the battle on the strength mismatch).
Fix: battle_engine.py:1158 `[0,0,4,3,0]` -> `[0,0,3,4,0]` (last row of the count == 5 table).

Run from the worktree root with the test folder on the path, e.g.
  run_pytest_odul.py -q -p no:cacheprovider --rootdir . <this file>  (PYTHONPATH=<wt>;<wt>\\test)
"""
from flask import Flask

import battle_engine
from battle_reward_test import chip_damage, client, item, power_damage, setup

app = Flask(__name__)
app.secret_key = 'test'


def test_a_flak_barrage_on_the_fifth_of_five_hits_its_neighbours_like_the_client(monkeypatch):
    with app.test_request_context():
        setup(monkeypatch, ["U05"], ["U05"] * 5)
        strength = client.strength("U05")
        left = [strength] * 5
        battle_engine.apply_consumable_direct_impact({}, item("N80"), 4, [item("U05")] * 5, left, {}, False, [])
        hits = [power_damage("N80", "U05") if i == 4 else chip_damage("N80", 5, 4, i) for i in range(5)]
        assert hits == [0, 0, 3, 4, 30]
        assert left == [strength - h for h in hits]
