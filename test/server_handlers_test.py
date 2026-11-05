"""The game calls that spend or grant cash, resources and items, end to end: AMF batches through the server's real
gateway and save game layer (flask-session with SQLAlchemy and msgspec, save.db in a temporary folder), each save
read back from the database after the call (`server`: the app as configure_app sets it up, conftest.py).

The expected values come from the client (assets/ZGame.109338.swf, read with turkce/araclar/abc.py: what the client
changes locally before it sends the call, the server must store the same, or the next load shows other numbers) and
from assets/29oct2012/gameSettings_with_fixes.xml, read here with ElementTree, not with the server's lookups."""
import copy
import itertools
import json
import os
import time
import xml.etree.ElementTree as ET

import libscrc
import pytest

import logger
from session_layer_test import INIT_USER, batch, new_save, stored

empires_server = __import__('empires-server')

HERE = os.path.dirname(__file__)
XML = ET.parse(os.path.join(HERE, "..", "assets", "29oct2012", "gameSettings_with_fixes.xml")).getroot()
ITEMS = {item.get("code"): item for item in XML.find("items").findall("item")}
CALL_FAILED = empires_server.CALL_FAILED


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(logger.socketio, "emit", lambda *args, **kwargs: None)  # no log page in tests
    monkeypatch.setattr(empires_server.settings, "crash_log", False)


UIDS = itertools.count(700_000_000_001)  # not the uid of a bot (bot_empires.FIRST_UID 900_000_000_001 and up)


def player_save(app, edit=lambda user_object: None):
    """A client with a new player's save game (test/init_user.json) of its own uid, changed by edit(user_object) before
    it is saved, its save id and the uid. lastEnergyCheck is now: handle_quest_progress replenishes energy every
    300 s since then, not during a test."""
    user_object = copy.deepcopy(INIT_USER)
    uid = next(UIDS)
    user_object["userInfo"]["player"]["uid"] = uid
    user_object["userInfo"]["player"]["lastEnergyCheck"] = time.time()
    edit(user_object)
    client, sid = new_save(app, user_object=user_object, quests=[], fleets={}, battle=None, population=None)
    return client, sid, uid


def world_objects(user_object):
    return user_object["userInfo"]["world"]["objects"]


def inventory(user_object):
    return user_object["userInfo"]["player"]["inventory"]["items"]


def player(save):
    return save["user_object"]["userInfo"]["player"]


def resources(save):
    return save["user_object"]["userInfo"]["world"]["resources"]


def zid(sid):
    """The visitor's id the server uses in other saves (game_settings.get_zid): ISO CRC-64 of the save id // 2048."""
    return libscrc.iso(sid.encode()) // 2048


def xml_cash(code):
    return int(ITEMS[code].find("cost").get("cash"))


def xml_resource_types():
    """<resources><resource index type>: the market sends the index (WorldResourceManager.getResourceTypeFromIndex)."""
    return {int(e.get("index")): e.get("type") for e in XML.find("resources").findall("resource")}


def a_plain_cash_item():
    """A consumable bought with cash into the inventory: no limited edition (requiredDate, GameItem.getModifiedCash
    gives limited editions a discount), no resource and not an expansion key (buy_item treats those apart)."""
    return next(item for item in ITEMS.values()
                if item.get("type") == "consumable" and item.get("buyable") == "true"
                and item.find("cost") is not None and int(item.find("cost").get("cash", "0")) > 0
                and item.find("requiredDate") is None and item.get("subtype") not in ("expansion", "energy", "refill")
                and item.get("resourceType") is None)


# UserService.buyItem


def test_buying_an_item_with_cash_puts_it_in_the_inventory(server):
    """Player.buyGameItem / UI.buyAndAddToInventory: Player.buyItem with useCash takes item.cash * amount (item.cash =
    GameItem.getModifiedCash(1) = ceil(xmlCash) without price tests) and addToInventory(code, amount) adds amount;
    TBuyItem.data sends code, useCash and amount. Nothing else is paid with cash."""
    item = a_plain_cash_item()
    code = item.get("code")
    client, sid, _ = player_save(server)
    before = stored(server, sid)

    answers = batch(client, ("UserService.buyItem", [{"code": code, "useCash": True, "amount": 3}]))

    assert answers[0]["errorType"] == 0
    after = stored(server, sid)
    assert player(after)["cash"] == player(before)["cash"] - 3 * xml_cash(code)
    assert player(after)["inventory"]["items"] == dict(player(before)["inventory"]["items"], **{code: 3})
    assert resources(after) == resources(before)


def test_buying_more_of_an_item_adds_to_what_the_inventory_has(server):
    item = a_plain_cash_item()
    code = item.get("code")
    client, sid, _ = player_save(server, lambda user_object: inventory(user_object).update({code: 4}))

    batch(client, ("UserService.buyItem", [{"code": code, "useCash": True, "amount": 2}]))

    assert player(stored(server, sid))["inventory"]["items"][code] == 4 + 2  # Player.addToInventory adds


def test_buying_resources_with_cash_adds_their_yield(server):
    """UI.onMarketClick, resource: Player.buyItem(item, useCash) takes item.cash, then
    resources.updateResourceAmount(resourceType, resourceYield), and sends TBuyItem(code, useCash, 1).
    RS07 in the XML: resource07, resourceType oil, cost cash 5, resourceYield 50."""
    item = ITEMS["RS07"]
    resource_type, resource_yield = item.get("resourceType"), int(item.find("resourceYield").text)
    client, sid, _ = player_save(server)
    before = stored(server, sid)

    answers = batch(client, ("UserService.buyItem", [{"code": "RS07", "useCash": True, "amount": 1}]))

    assert answers[0]["errorType"] == 0
    after = stored(server, sid)
    assert player(after)["cash"] == player(before)["cash"] - xml_cash("RS07")
    assert resources(after) == dict(resources(before), **{resource_type: resources(before)[resource_type]
                                                          + resource_yield})
    assert player(after)["inventory"] == player(before)["inventory"]  # a resource is not an inventory item


def test_buying_rare_resources_with_coins(server):
    """Player.buyItem without cash: xp += GameSettingsInit.getBuyXp(coins) = max(floor(coins * buyXpGainRatio),
    buyXpGainMin) = 0 (both 0 in the XML), then each resourceCost: updateResourceAmount(type, -amount * n).
    UI.onMarketClick then adds resourceYield. RS11 in the XML: resource01a, aluminum, cost coins 4000, yield 10."""
    item = ITEMS["RS11"]
    coins = int(item.find("cost").get("coins"))
    resource_type, resource_yield = item.get("resourceType"), int(item.find("resourceYield").text)
    assert XML.find("gamesettings").get("buyXpGainRatio") == "0" and XML.find("gamesettings").get("buyXpGainMin") == "0"
    client, sid, _ = player_save(server)
    before = stored(server, sid)  # init_user.json: 5000 coins, enough for one

    answers = batch(client, ("UserService.buyItem", [{"code": "RS11", "useCash": False, "amount": 1}]))

    assert answers[0]["errorType"] == 0
    after = stored(server, sid)
    assert resources(after) == dict(resources(before), coins=resources(before)["coins"] - coins,
                                    **{resource_type: resources(before)[resource_type] + resource_yield})
    assert (player(after)["cash"], player(after)["xp"]) == (player(before)["cash"], player(before)["xp"])


def test_buying_an_unknown_item_changes_nothing(server):
    """There is no item with this code in the XML: the call fails, its changes are undone (guarded_call)."""
    assert "NOSUCH" not in ITEMS
    client, sid, _ = player_save(server)
    before = stored(server, sid)

    answers = batch(client, ("UserService.buyItem", [{"code": "NOSUCH", "useCash": True, "amount": 1}]))

    assert answers[0]["errorType"] == CALL_FAILED
    assert stored(server, sid) == before


# UserService.buyExpansion


def test_buying_an_expansion_sets_its_bit(server):
    """GMExpansion.buyExpansion: player.expansions.setBit(m_lastValidIndex), TBuyExpansion sends that index.
    BitArray.setBit: m_data[index >> 5] |= 1 << (index - (index >> 5 << 5)) (SHIFTS_PER_INDEX 5).
    Index 37: word 1, bit 5; init_user.json's word 1 is 0 and 37 is not a starting expansion (90,91,104,...)."""
    assert "37" not in XML.find("gamesettings").get("startingExpansionIndexes").split(",")
    client, sid, _ = player_save(server)
    before = stored(server, sid)
    data = list(player(before)["expansions"]["data"])
    assert data[1] == 0

    answers = batch(client, ("UserService.buyExpansion", [{"code": "x01", "useCash": False, "amount": 1, "index": 37,
                                                           "skipInventory": 1}]))

    assert answers[0]["errorType"] == 0
    data[1] |= 1 << 5
    assert player(stored(server, sid))["expansions"]["data"] == data


def test_an_expansion_bought_twice_stays_set(server):
    """setBit ors the bit in: the other bits of the word stay. Word 4 of init_user.json is 805306368 (bits 28, 29:
    the starting expansions 156, 157 would be there), index 4*32 + 3 = 131 adds bit 3."""
    client, sid, _ = player_save(server)
    data = list(player(stored(server, sid))["expansions"]["data"])
    call = ("UserService.buyExpansion", [{"code": "x01", "useCash": False, "amount": 1, "index": 131,
                                          "skipInventory": 1}])

    batch(client, call)
    batch(client, call)

    data[4] |= 1 << 3
    assert player(stored(server, sid))["expansions"]["data"] == data


# WorldService.performAction on a Market: add / list / remove (TMarketAdd, TMarketList, TMarketRemove)


MARKET_ID = 990001


def market_save(server):
    """A save with a Market (XML R00, className Market) in its world."""
    client, sid, _ = player_save(server, lambda user_object: world_objects(user_object).append(
        {"id": MARKET_ID, "itemName": ITEMS["R00"].get("name"), "position": "40,40,0", "referenceItem": None,
         "state": 0}))
    return client, sid


def market_action(step, params):
    """TWorldState.signedWorldAction(step, m_params): [step, the object, [m_params]]."""
    return ("WorldService.performAction", [step, {"id": MARKET_ID, "position": "40,40,0", "itemName": "Market"},
                                           [params]])


def stored_market(save):
    return next(e for e in save["user_object"]["userInfo"]["world"]["objects"] if e["id"] == MARKET_ID)


def test_putting_resources_on_the_market_takes_them(server):
    """MarketHost.onAdd takes the units from its copy of the resources (m_worldResourceAmounts[type of the index] -=
    RESOURCE_INCREMENT, again for each increment), MarketHost.onSuccess makes that copy the player's resources.
    TMarketAdd sends {item: index, units, type: 'resource'} (TYPE_RESOURCE = 'resource')."""
    index, units = 3, 200
    resource_type = xml_resource_types()[index]
    client, sid = market_save(server)
    before = stored(server, sid)
    assert resources(before)[resource_type] >= units  # init_user.json: 1000 aluminum

    answers = batch(client, market_action("add", {"item": index, "units": units, "type": "resource"}),
                    market_action("list", {}))

    assert [a["errorType"] for a in answers] == [0, 0]
    after = stored(server, sid)
    assert resources(after) == dict(resources(before), **{resource_type: resources(before)[resource_type] - units})
    order = {"type": "resource", "item": index, "units": units}
    assert {k: stored_market(after)[k] for k in order} == order
    assert {k: answers[1]["data"][0][k] for k in order} == order  # TMarketList: what the market sells


def test_taking_resources_off_the_market_gives_them_back(server):
    """MarketHost.onRemove gives the units back to its copy of the resources (+= units); TMarketRemove sends
    {units, item}; the answer is ['success'] (TMarketRemove.onComplete: data[0] == 'success' else onFail)."""
    index, units = 1, 20
    resource_type = xml_resource_types()[index]
    client, sid = market_save(server)
    before = stored(server, sid)

    batch(client, market_action("add", {"item": index, "units": units, "type": "resource"}))
    answers = batch(client, market_action("remove", {"item": index, "units": units}))

    assert answers[0]["data"] == ["success"]
    after = stored(server, sid)
    assert resources(after) == resources(before)
    assert {k: stored_market(after)[k] for k in ("type", "item", "units")} == dict.fromkeys(("type", "item", "units"))


# UserService.useItem


def test_using_an_item_takes_one_from_the_inventory(server):
    """UI.tryUsePlayerEnergies: removeInventoryItem(code) (one) and TUseItem sends the code."""
    client, sid, _ = player_save(server, lambda user_object: inventory(user_object).update(EN1=2))

    answers = batch(client, ("UserService.useItem", ["EN1"]))

    assert answers[0]["errorType"] == 0
    assert player(stored(server, sid))["inventory"]["items"]["EN1"] == 1


def test_using_an_item_that_is_not_in_the_inventory_changes_nothing(server):
    """Player.removeInventoryItem: an item the inventory doesn't have is not taken (returns false)."""
    client, sid, _ = player_save(server)
    before = stored(server, sid)
    assert "EN1" not in player(before)["inventory"]["items"]

    answers = batch(client, ("UserService.useItem", ["EN1"]))

    assert answers[0]["errorType"] == CALL_FAILED
    assert stored(server, sid) == before


def test_bought_expansion_keys_go_to_the_inventory(server):
    """xk01 (expansionkey01: type consumable, subtype expansion, cost cash 2). Player.buyGameItem and
    Player.buyMultiRequirementItem (TBuyItems) add it to the inventory: addToInventory(code, amount). Only items of
    type expansion (x01..x03) are not kept in the inventory."""
    client, sid, _ = player_save(server)
    before = stored(server, sid)

    batch(client, ("UserService.buyItem", [{"code": "xk01", "useCash": True, "amount": 3}]))

    after = stored(server, sid)
    assert player(after)["cash"] == player(before)["cash"] - 3 * xml_cash("xk01")
    assert inventory(after["user_object"]).get("xk01", 0) == 3


def test_using_an_energy_item_gives_its_energy(server):
    """UI.tryUsePlayerEnergies: m_energy.energy += referenceItem.energyYield (not capped), removeInventoryItem(code),
    then TUseItem. EN1 (energy01): energyYield 1 in the XML."""
    def edit(user_object):
        inventory(user_object).update(EN1=1)
        user_object["userInfo"]["player"]["energy"] = 10
    client, sid, _ = player_save(server, edit)

    batch(client, ("UserService.useItem", ["EN1"]))

    assert player(stored(server, sid))["energy"] == 10 + int(ITEMS["EN1"].find("energyYield").text)


def test_an_energy_refill_is_paid(server):
    """EnergyRefillItem.refillAmount = energyMax - energy; UI.buyAndAddToInventory: Player.buyItem(ERX, useCash) takes
    EnergyRefillItem.cash = ceil(refillAmount * costMultiplierByType('energypurchase')) = refillAmount (no price tests:
    priceTestSettings {}), then TPurchaseEnergyRefill. The server used to fill the energy first and then take
    energyMax - energy = 0 cash."""
    def edit(user_object):
        user_object["userInfo"]["player"].update(energy=5, energyMax=25, cash=100)
    client, sid, _ = player_save(server, edit)

    batch(client, ("UserService.purchaseEnergyRefill", [{"code": "ERX", "useCash": True, "amount": 1}]))

    after = player(stored(server, sid))
    assert (after["energy"], after["cash"]) == (25, 100 - (25 - 5))


# UserService.setWorldName


def test_the_new_world_name_is_saved(server):
    """TRenameWorld.perform sends the name, the server keeps it as the world name."""
    client, sid, _ = player_save(server)

    answers = batch(client, ("UserService.setWorldName", ["Yeni Ülke"]))

    assert answers[0]["errorType"] == 0
    assert stored(server, sid)["user_object"]["userInfo"]["worldName"] == "Yeni Ülke"


# PVPService.pillage


def invaded_save(server, visitor_sid):
    """Another player's save that the visitor invaded: pvp.invaders has 'u' + the visitor's zid."""
    _, sid, uid = player_save(server, lambda user_object: user_object["pvp"]["invaders"].update(
        {"u" + str(zid(visitor_sid)): {"pos": "10,10,0"}}))
    return sid, uid


def test_pillaging_marks_the_time_in_the_invaded_save(server):
    """PVPManager.doPillage sends TPVPPillage(hostPlayer.uid), m_hostID is a String, and sets pvpInfo.pillTS = serverTime / 1000: seconds,
    the invaded player's invader entry of the visitor gets that time."""
    client, sid, _ = player_save(server)
    host_sid, host_uid = invaded_save(server, sid)
    start = time.time()

    answers = batch(client, ("PVPService.pillage", [str(host_uid)]))

    assert answers[0]["errorType"] == 0
    invader = stored(server, host_sid)["user_object"]["pvp"]["invaders"]["u" + str(zid(sid))]
    assert start <= invader["pillTS"] <= time.time()
    assert invader["pos"] == "10,10,0"


def test_pillaging_a_save_the_visitor_did_not_invade_changes_nothing(server):
    client, sid, _ = player_save(server)
    host_client, host_sid, host_uid = player_save(server)
    before = stored(server, host_sid)

    answers = batch(client, ("PVPService.pillage", [str(host_uid)]))

    assert answers[0]["errorType"] == CALL_FAILED
    assert stored(server, host_sid) == before


# WorldService.loadWorld


def load_world(uid):
    return [str(uid), "home", 0, {}]  # TWorldLoad.perform, VISIT_MODE_NONE 0


def test_loading_the_own_world_gives_the_save(server):
    """TWorldLoad.perform sends [m_userId.toString(), m_mapName 'home', m_pvpMode, m_dbg]: for the player's own uid
    the answer is the save's own userInfo: its player too (here with xp 4321 and 77 cash, a new player has neither)."""
    def edit(user_object):
        user_object["userInfo"]["player"].update(xp=4321, cash=77)
    client, sid, uid = player_save(server, edit)
    before = stored(server, sid)

    answers = batch(client, ("WorldService.loadWorld", load_world(uid)))

    data = answers[0]["data"]
    assert data["worldName"] == before["user_object"]["userInfo"]["worldName"]
    assert data["world"]["objects"] == before["user_object"]["userInfo"]["world"]["objects"]
    assert (data["player"]["uid"], data["player"]["xp"], data["player"]["cash"]) == (uid, 4321, 77)
    assert stored(server, sid)["user_object"]["userInfo"]["world"] == before["user_object"]["userInfo"]["world"]


def test_visiting_an_ally_shows_its_island(server):
    """An ally of allies/: its island file's objects, roads and world name (read here from the file itself)."""
    with open(os.path.join(HERE, "..", "allies", "AcidCaos-island.json"), encoding="utf-8") as f:
        island = json.load(f)
    uid = island["info"]["uid"] if island["info"] else island["friend"]["uid"]
    client, sid, _ = player_save(server)

    answers = batch(client, ("WorldService.loadWorld", load_world(uid)))

    data = answers[0]["data"]
    assert data["player"]["uid"] == uid
    assert data["world"]["objects"] == island["objects"]
    if "worldName" in island:
        assert data["worldName"] == island["worldName"]


def test_visiting_another_local_save_shows_its_world(server):
    other_client, other_sid, other_uid = player_save(server)
    batch(other_client, ("UserService.setWorldName", ["Komşu"]))
    other = stored(server, other_sid)
    client, sid, _ = player_save(server)

    answers = batch(client, ("WorldService.loadWorld", load_world(other_uid)))

    data = answers[0]["data"]
    assert data["player"]["uid"] == other_uid
    assert data["worldName"] == "Komşu"
    assert data["world"]["objects"] == other["user_object"]["userInfo"]["world"]["objects"]
    assert stored(server, other_sid) == other  # a visit doesn't change the visited save


# VisitorService.help / accept / decline


ROCK_ID = 990002


def rock_save(server, help_requests=None):
    """A save with a rock (XML S17 rock01, subtype rock, DefaultPropStateMachine) in its world, in state 0 'placed':
    clickNext 1, visitorHelpType 'clear'; and these help requests of visitors."""
    def edit(user_object):
        world_objects(user_object).append({"id": ROCK_ID, "itemName": ITEMS["S17"].get("name"),
                                           "position": "30,30,0", "referenceItem": None, "state": 0, "lastUpdated": 0})
        if help_requests is not None:
            user_object["visitorHelpRequests"] = help_requests
    return player_save(server, edit)


def test_helping_a_neighbor_asks_it_to_accept_and_rewards_the_visitor(server):
    """TVisitorHelp sends [m_neighborID (String), m_objID (int), the state's visitorHelpType]. The neighbor's save keeps the help
    for it to accept (visitorHelpRequests[visitor zid] = object ids, comma separated). The visitor gets the
    visitorRewards reward 'clear' + the item's subtype: clearrock, coins 25 and socialXpGood 1 in the XML."""
    _, host_sid, host_uid = rock_save(server)
    client, sid, _ = player_save(server)
    before = stored(server, sid)
    [reward] = [e for e in XML.find("visitorRewards").findall("reward") if e.get("name") == "clear" +
                ITEMS["S17"].get("subtype")]

    answers = batch(client, ("VisitorService.help", [str(host_uid), ROCK_ID, "clear"]))

    assert answers[0]["errorType"] == 0
    after = stored(server, sid)
    assert resources(after) == dict(resources(before), coins=resources(before)["coins"] + int(reward.get("coins")))
    assert player(after)["socialXpGood"] == player(before)["socialXpGood"] + int(reward.get("socialXpGood"))
    host = stored(server, host_sid)
    assert host["user_object"]["visitorHelpRequests"] == {str(zid(sid)): str(ROCK_ID)}
    rock = next(e for e in host["user_object"]["userInfo"]["world"]["objects"] if e["id"] == ROCK_ID)
    assert rock["state"] == 0  # the owner's world changes when the owner accepts


def test_more_help_of_the_same_visitor_is_added(server):
    _, host_sid, host_uid = rock_save(server)
    client, sid, _ = player_save(server)

    batch(client, ("VisitorService.help", [str(host_uid), ROCK_ID, "clear"]))
    batch(client, ("VisitorService.help", [str(host_uid), ROCK_ID, "clear"]))

    assert stored(server, host_sid)["user_object"]["visitorHelpRequests"] == {
        str(zid(sid)): str(ROCK_ID) + "," + str(ROCK_ID)}


def test_accepted_help_clears_the_rock(server):
    """TVisitorAccept sends [m_neighborID] (String), the visitor: the helped objects make their click as if the owner made it, without its
    energy cost. DefaultPropStateMachine: 0 clickNext 1, 1 and 2 autoNext after 0s, so the rock is in
    clearedState 3 (dormant); the help is used up."""
    machine = next(e for e in XML.find("stateMachines").findall("stateMachine")
                   if e.get("name") == "DefaultPropStateMachine")
    client, sid, _ = rock_save(server, {"12345": str(ROCK_ID)})
    before = stored(server, sid)

    answers = batch(client, ("VisitorService.accept", ["12345"]))

    assert answers[0]["errorType"] == 0
    after = stored(server, sid)
    assert after["user_object"]["visitorHelpRequests"] == {}
    rock = next(e for e in after["user_object"]["userInfo"]["world"]["objects"] if e["id"] == ROCK_ID)
    assert str(rock["state"]) == machine.get("clearedState")
    assert player(after)["energy"] == player(before)["energy"]


def test_declined_help_changes_only_the_requests(server):
    client, sid, _ = rock_save(server, {"12345": str(ROCK_ID), "678": str(ROCK_ID)})
    before = stored(server, sid)

    answers = batch(client, ("VisitorService.decline", ["12345"]))

    assert answers[0]["errorType"] == 0
    after = stored(server, sid)
    assert after["user_object"]["visitorHelpRequests"] == {"678": str(ROCK_ID)}
    assert after["user_object"]["userInfo"] == before["user_object"]["userInfo"]
