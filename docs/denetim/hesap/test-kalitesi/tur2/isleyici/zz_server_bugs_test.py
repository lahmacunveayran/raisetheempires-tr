"""Tests that fail on the server of cb00c06: differences between what the client changes locally and what the server
stores. Not committed (empires-server.py is not mine). To run: copy into test/ and run it there with the launcher."""
from server_handlers_test import *  # noqa: F401,F403  the server fixture, quiet, helpers
from server_handlers_test import (ITEMS, XML, batch, inventory, player, player_save, resources, stored, xml_cash,
                                  a_plain_cash_item, CALL_FAILED)


def test_bought_expansion_keys_go_to_the_inventory(server):
    """xk01 (expansionkey01, type consumable, subtype expansion, cost cash 2): Player.buyGameItem /
    Player.buyMultiRequirementItem (TBuyItems) add it to the inventory: addToInventory(code, amount).
    buy_item's `elif item.get("-subtype") == "expansion"` branch skips the inventory for it."""
    client, sid, _ = player_save(server)
    before = stored(server, sid)

    batch(client, ("UserService.buyItem", [{"code": "xk01", "useCash": True, "amount": 3}]))

    after = stored(server, sid)
    assert player(after)["cash"] == player(before)["cash"] - 3 * xml_cash("xk01")
    assert inventory(after["user_object"]).get("xk01", 0) == 3


def test_the_first_expansion_costs_its_xml_price(server):
    """GMExpansion.buyExpansion: Player.buyItem(x01, useCash false, 1): resourceCosts (coins) and itemCosts (xk01).
    ExpansionItem.getAmount(cost, scalar) = cost * scalar^n, n = expansions.numBitsSet() - number of
    startingExpansionIndexes; a new save has only the 6 starting bits, so n = 0: 5000 coins and 10 xk01
    (<cost coins="5000"/><itemcost xk01="10"/>). buy_expansion_response only sets the bit."""
    item = ITEMS["x01"]
    coins, keys = int(item.find("cost").get("coins")), int(item.find("itemcost").get("xk01"))
    client, sid, _ = player_save(server, lambda user_object: inventory(user_object).update(xk01=keys))
    before = stored(server, sid)

    batch(client, ("UserService.buyExpansion", [{"code": "x01", "useCash": False, "amount": 1, "index": 37,
                                                 "skipInventory": 1}]))

    after = stored(server, sid)
    assert resources(after)["coins"] == resources(before)["coins"] - coins
    assert inventory(after["user_object"]).get("xk01", 0) == 0


def test_using_an_energy_item_gives_its_energy(server):
    """UI.tryUsePlayerEnergies: m_energy.energy += referenceItem.energyYield, removeInventoryItem(code), then TUseItem.
    EN1 (energy01): energyYield 1. use_item_response only takes the item."""
    def edit(user_object):
        inventory(user_object).update(EN1=1)
        user_object["userInfo"]["player"]["energy"] = 10
    client, sid, _ = player_save(server, edit)

    batch(client, ("UserService.useItem", ["EN1"]))

    assert player(stored(server, sid))["energy"] == 10 + int(ITEMS["EN1"].find("energyYield").text)


def test_an_energy_refill_is_paid(server):
    """EnergiserManager / BuyEnergyCard: EnergyRefillItem.refillAmount = energyMax - energy; UI.buyAndAddToInventory:
    Player.buyItem(ERX, useCash) takes EnergyRefillItem.cash = ceil(refillAmount * costMultiplierByType
    ('energypurchase')) = refillAmount (no price tests: priceTestSettings {}), then TPurchaseEnergyRefill.
    purchase_energy_refill_response fills the energy first and then takes energyMax - energy = 0 cash."""
    def edit(user_object):
        user_object["userInfo"]["player"].update(energy=5, energyMax=25, cash=100)
    client, sid, _ = player_save(server, edit)

    batch(client, ("UserService.purchaseEnergyRefill", [{"code": "ERX", "useCash": True, "amount": 1}]))

    after = player(stored(server, sid))
    assert (after["energy"], after["cash"]) == (25, 100 - (25 - 5))


def test_buying_without_enough_cash_changes_nothing(server):
    """The server takes the cash the client says it spends, also below 0 (the client's market only offers what the
    player can pay, Player.buyItem itself does not check)."""
    item = a_plain_cash_item()
    client, sid, _ = player_save(server, lambda user_object: user_object["userInfo"]["player"].update(cash=0))
    before = stored(server, sid)

    answers = batch(client, ("UserService.buyItem", [{"code": item.get("code"), "useCash": True, "amount": 1}]))

    assert answers[0]["errorType"] == CALL_FAILED
    assert stored(server, sid) == before
