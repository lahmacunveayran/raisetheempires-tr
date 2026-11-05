import sys
p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:60], s.count(old))
    s = s.replace(old, new)

rep('''def test_pillaging_marks_the_time_in_the_invaded_save(server):
    """PVPManager.doPillage sends TPVPPillage(hostPlayer.uid) and sets''',
'''def test_pillaging_marks_the_time_in_the_invaded_save(server):
    """PVPManager.doPillage sends TPVPPillage(hostPlayer.uid), m_hostID is a String, and sets''')
rep('("PVPService.pillage", [host_uid])', '("PVPService.pillage", [str(host_uid)])', 2)
rep('''    """TWorldLoad sends [uid, ?, pvpMode]: for the player's own uid the answer is the save's own userInfo."""''',
'''    """TWorldLoad.perform sends [m_userId.toString(), m_mapName 'home', m_pvpMode, m_dbg]: for the player's own uid
    the answer is the save's own userInfo."""''')
rep('("WorldService.loadWorld", [uid, 0, False])', '("WorldService.loadWorld", load_world(uid))', 2)
rep('("WorldService.loadWorld", [other_uid, 0, False])', '("WorldService.loadWorld", load_world(other_uid))')
rep('''# WorldService.loadWorld
''', '''# WorldService.loadWorld


def load_world(uid):
    return [str(uid), "home", 0, {}]  # TWorldLoad.perform, VISIT_MODE_NONE 0
''')
rep('''    """TVisitorHelp sends [neighbor uid, object id, the state's visitorHelpType].''',
'''    """TVisitorHelp sends [m_neighborID (String), m_objID (int), the state's visitorHelpType].''')
rep('("VisitorService.help", [host_uid, ROCK_ID, "clear"])', '("VisitorService.help", [str(host_uid), ROCK_ID, "clear"])', 3)
rep('''    """VisitorService.accept [visitor id]:''', '''    """TVisitorAccept sends [m_neighborID] (String), the visitor:''')
open(p, "w", encoding="utf-8", newline="").write(s)
