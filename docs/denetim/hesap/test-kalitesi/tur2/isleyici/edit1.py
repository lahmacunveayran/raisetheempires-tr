import sys
p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:60], s.count(old))
    s = s.replace(old, new)

rep('''def player_save(app, **changes):
    """A client with a new player's save game (test/init_user.json) of its own uid, its save id and the uid.
    lastEnergyCheck is now: handle_quest_progress replenishes energy every 300 s since then, not during a test."""
    user_object = copy.deepcopy(INIT_USER)
    uid = next(UIDS)
    user_object["userInfo"]["player"]["uid"] = uid
    user_object["userInfo"]["player"]["lastEnergyCheck"] = time.time()
    values = dict(user_object=user_object, quests=[], fleets={}, battle=None, population=None)
    values.update(changes)
    client, sid = new_save(app, **values)
    return client, sid, uid
''', '''def player_save(app, edit=lambda user_object: None):
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
''')

rep('''    client, sid, _ = player_save(server)
    save = stored(server, sid)
    save["user_object"]["userInfo"]["player"]["inventory"]["items"][code] = 4
    client, sid, _ = player_save(server, user_object=save["user_object"])
''', '''    client, sid, _ = player_save(server, lambda user_object: inventory(user_object).update({code: 4}))
''')

rep('''    client, sid, uid = player_save(server)
    save = stored(server, sid)
    save["user_object"]["userInfo"]["world"]["objects"].append(
        {"id": MARKET_ID, "itemName": ITEMS["R00"].get("name"), "position": "40,40,0", "referenceItem": None,
         "state": 0})
    return new_save(server, **{k: v for k, v in save.items() if k != "session_id"})
''', '''    client, sid, _ = player_save(server, lambda user_object: world_objects(user_object).append(
        {"id": MARKET_ID, "itemName": ITEMS["R00"].get("name"), "position": "40,40,0", "referenceItem": None,
         "state": 0}))
    return client, sid
''')

rep('''    client, sid, _ = player_save(server)
    save = stored(server, sid)
    player(save)["inventory"]["items"]["EN1"] = 2
    client, sid = new_save(server, **{k: v for k, v in save.items() if k != "session_id"})
''', '''    client, sid, _ = player_save(server, lambda user_object: inventory(user_object).update(EN1=2))
''')

rep('''    client, sid, uid = player_save(server)
    save = stored(server, sid)
    save["user_object"]["pvp"]["invaders"]["u" + str(zid(visitor_sid))] = {"pos": "10,10,0"}
    client, sid = new_save(server, **{k: v for k, v in save.items() if k != "session_id"})
    player(save)["uid"] = uid
    return sid, uid
''', '''    _, sid, uid = player_save(server, lambda user_object: user_object["pvp"]["invaders"].update(
        {"u" + str(zid(visitor_sid)): {"pos": "10,10,0"}}))
    return sid, uid
''')

rep('''def rock_save(server, **changes):
    """A save with a rock (XML S17 rock01, subtype rock, DefaultPropStateMachine) in its world, in state 0 'placed':
    clickNext 1, visitorHelpType 'clear'."""
    client, sid, uid = player_save(server, **changes)
    save = stored(server, sid)
    save["user_object"]["userInfo"]["world"]["objects"].append(
        {"id": ROCK_ID, "itemName": ITEMS["S17"].get("name"), "position": "30,30,0", "referenceItem": None,
         "state": 0, "lastUpdated": 0})
    client, sid = new_save(server, **{k: v for k, v in save.items() if k != "session_id"})
    return client, sid, uid
''', '''def rock_save(server, help_requests=None):
    """A save with a rock (XML S17 rock01, subtype rock, DefaultPropStateMachine) in its world, in state 0 'placed':
    clickNext 1, visitorHelpType 'clear'; and these help requests of visitors."""
    def edit(user_object):
        world_objects(user_object).append({"id": ROCK_ID, "itemName": ITEMS["S17"].get("name"),
                                           "position": "30,30,0", "referenceItem": None, "state": 0, "lastUpdated": 0})
        if help_requests is not None:
            user_object["visitorHelpRequests"] = help_requests
    return player_save(server, edit)
''')

rep('''    client, sid, _ = rock_save(server, )
    save = stored(server, sid)
    save["user_object"]["visitorHelpRequests"] = {"12345": str(ROCK_ID)}
    client, sid = new_save(server, **{k: v for k, v in save.items() if k != "session_id"})
    before''', '''    client, sid, _ = rock_save(server, {"12345": str(ROCK_ID)})
    before''')

rep('''    client, sid, _ = rock_save(server)
    save = stored(server, sid)
    save["user_object"]["visitorHelpRequests"] = {"12345": str(ROCK_ID), "678": str(ROCK_ID)}
    client, sid = new_save(server, **{k: v for k, v in save.items() if k != "session_id"})
    before''', '''    client, sid, _ = rock_save(server, {"12345": str(ROCK_ID), "678": str(ROCK_ID)})
    before''')
open(p, "w", encoding="utf-8", newline="").write(s)
