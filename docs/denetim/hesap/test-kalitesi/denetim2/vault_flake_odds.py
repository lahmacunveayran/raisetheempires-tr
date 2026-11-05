"""How often test_every_vault_can_give_each_of_its_prizes (treasure_vault_test.py) fails by chance, and what it lets
through. treasure_vault.spin_response draws with the unseeded random.choices (treasure_vault.py:112).
Run from the repository folder:  python vault_flake_odds.py
"""
import os
import random
import sys

sys.path.insert(0, os.getcwd())
import treasure_vault  # noqa: E402

SPINS, SIMS = 400, 20000
rng = random.Random(0)
for tier, loot in treasure_vault.LOOT.items():
    weights = [w for _, _, w in loot]
    codes = [c if c not in treasure_vault.RESOURCES else "res" for c, _, _ in loot]
    needed = len([c for c in codes if c != "res"])
    fails = missed_but_passed = 0
    p_item = {c: w / sum(weights) for c, w in zip(codes, weights) if c != "res"}
    for _ in range(SIMS):
        seen = set(rng.choices(codes, weights=weights, k=SPINS))
        missing = [c for c in p_item if c not in seen]
        if len(seen) < needed:
            fails += 1
        elif missing:
            missed_but_passed += 1
    rarest = min(p_item, key=p_item.get)
    print("tier %s: %d item prizes, resource prize: %s, rarest %s p=%.4f; P(test fails)=%.5f; "
          "P(an item never came but the test passed)=%.5f"
          % (tier, needed, "res" in codes, rarest, p_item[rarest], fails / SIMS, missed_but_passed / SIMS))
