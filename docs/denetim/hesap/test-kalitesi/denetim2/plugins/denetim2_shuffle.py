"""pytest plugin (denetim2): runs the tests in a random order, seeded by the SHUFFLE_SEED environment variable.
SHUFFLE_SEED=reverse runs them in reverse collection order."""
import os
import random


def pytest_collection_modifyitems(session, config, items):
    seed = os.environ.get("SHUFFLE_SEED")
    if not seed:
        return
    if seed == "reverse":
        items.reverse()
    else:
        random.Random(int(seed)).shuffle(items)
    print("\n[shuffle] order seed", seed, "first:", items[0].nodeid)
