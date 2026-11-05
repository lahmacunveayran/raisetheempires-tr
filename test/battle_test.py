#TO RUN TESTS RUN empires_test.py
"""init_battle, the powers and the fleet helpers. The units a battle has are worked out here from the input (the fleets
of the session) or from the quest XML (questSettings_with_fixes.xml: <task action="fight" item> is the enemy fleet item
of gameSettings_with_fixes.xml, its <baddie item> the enemy units, <fleet> the units the quest gives the player), the
strengths from the game XML (battle_reward_test reads both with ElementTree), never from the server's own item dicts."""

import battle_engine
import client_settings as client
from flask import Flask, session

from battle_reward_test import UNIQUE_NUMBER, chip_damage, fight_baddies, island_strength, items, modifier_of, \
    power_damage, researched_strength, task_fleet, tasks


app = Flask(__name__)
app.secret_key = 'test'

# the fleets of setup_session: two UB96 of the player against the enemy fleet of island 2 of C037 (status 2 << 20)
OWN_UNITS = ['UB96,300,0,0,0', 'UB96,300,0,1,0']
ENEMY_FLEET = {'-U58': '1', '-SU02': '1', '-U63': '1'}
C037_ISLAND = 2097152 >> 20
# setup_session_invade: the player's fleet and the neighbour's FleetName
INVADE_OWN_UNITS = ['V06,180,1,0,0', 'V06,180,1,1,0', 'UN33,780,0,2,0', 'UN33,780,0,3,0', 'UL61,340,0,4,0']
INVADE_ENEMY_UNITS = ['V61,,,,', 'V61,,,,', 'U01,,,,', 'U01,,,,', 'U01,,,,']
RESEARCH = {'U43': ['XD01', 'XA01', 'XT01'], 'U45': ['XD01'], 'U44': ['XD01'], 'U72': ['XD01', 'XA01'],
            'U48': ['XD02', 'XA02', 'XT02', 'XS02', 'XC02', 'XR02'], 'U15': ['XD04'],
            'V06': ['XD05', 'XT05', 'XA05', 'XC05', 'XR05', 'XS05'],
            'U60': ['XD04', 'XT04', 'XA04', 'XC04', 'XS04', 'XR04']}


def codes_of(unit_strings):
    return [u.split(',')[0] for u in unit_strings]


def codes_of_counts(fleet):
    return [code[1:] for code, count in fleet.items() for _ in range(int(count))]


def the_shield_power():
    """The power the shields research gives each unit at the start (N75: <consumable givesAbility="shield">)."""
    assert items()['N75'].find('consumable').get('givesAbility') == 'shield'
    return 'N75'


def has_shields_research(code, research):
    return any(modifier_of(u).get('shields') for u in research.get(code, []))


def test_init_battle():
    run_init_battle({'id': [0, 0], 'fleet': 'fleet14_2341959767162880', 'target': 'fleet15_2341959767162880', 'ch': 4858,
     'map': 'C037'})


def test_init_battle_consumable():
    run_init_battle({'id': 1, 'ch': 3207, 'level': 0, 'name': 'fleet15_2341959767162880', 'fleet': None, 'map': 'C037', 'code': 'N04'})


def test_init_battle_ai_consumable():
    # AI consumable
    run_init_battle({'id': 0, 'ch': 1329, 'level': 0, 'name': 'AI', 'fleet': None, 'map': 'C037', 'code': None})


def test_init_battle_ai():
    run_init_battle({'fleet': 'fleet14_2341959767162880', 'target': 'fleet15_2341959767162880', 'ch': 4861, 'map': 'C037'})


def test_init_battle_ally_consumable():
    run_init_battle({'id': 27, 'ch': 3416, 'level': 90, 'name': '123', 'fleet': 'fleet15_2341959767162880', 'map': 'C037', 'code': 'A0A'})


def test_init_battle_self_consumable():
    run_init_battle({'id': 0, 'ch': 3210, 'level': 0, 'name': 'fleet14_2341959767162880', 'fleet': None, 'map': 'C037', 'code': 'N06'})


def test_init_battle_invade():
    run_init_battle_invade({'target': 'FleetName', 'ch': 4673, 'attackHostId': '1207348428048663', 'id': [0, 0], 'fleet': 'fleet14_2341959767162880', 'map': None})


def test_init_battle_ai_invade():
    run_init_battle_invade({'fleet': 'fleet14_2341959767162880', 'target': 'FleetName', 'ch': 4673, 'attackHostId': '6709797546928099', 'map': None})


def test_init_battle_invade_consumable():
    run_init_battle_invade({'id': 0, 'ch': 2065, 'level': 0, 'name': 'FleetName', 'fleet': None, 'map': None, 'code': 'N04'})


def test_init_battle_invade_self_consumable():
    run_init_battle_invade({'id': 3, 'ch': 2985, 'level': 0, 'name': 'fleet14_2341959767162880', 'fleet': None, 'map': None, 'code': 'N02'})


def test_init_battle_ai_invade_consumable():
    # AI consumable
    run_init_battle_invade({'id': 0, 'ch': 1329, 'level': 0, 'name': 'AI', 'fleet': None, 'map': None, 'code': None})


#lvl 20 wave survival mode
# attack 1
#  fleets before {'fleet1_3398563345700246': None, 'fleet3_3398563345700246': None, 'fleet5_3398563345700246': None, 'fleet7_3398563345700246': None, 'fleet9_3398563345700246': None, 'fleet11_3398563345700246': None, 'FleetName': {'type': 'army', 'uid': 1, 'name': 'FleetName', 'status': 4096, 'target': '', 'consumables': [], 'inventory': [], 'playerLevel': 20, 'specialBits': None, 'lost': None, 'lastUnitLost': None, 'lastIndexLost': None, 'allies': None, 'battleTarget': None, 'battleTimestamp': None, 'ransomRandom': None, 'ransomResource': None, 'ransomAmount': None, 'units': ['V04,,,,', 'U05,,,,', 'SU03,,,,', 'V62,,,,'], 'store': [0], 'fleets': [], 'upgrades': None, 'hp': None, 'invader': True}, 'fleet12_3398563345700246': ['UN33,780,0,0,0', 'UN33,780,0,1,0', 'UN06,740,0,2,0', 'UN06,740,0,3,0', 'V06,180,1,4,0']}
# {'ch': 3833, 'fleet': 'fleet12_3398563345700246', 'target': 'FleetName', 'map': None, 'id': [0, 0]}
# def 1
# {'fleet': None, 'level': 0, 'id': 0, 'ch': 1221, 'map': None, 'name': 'AI', 'code': None}
# {'fleet1_3398563345700246': None, 'fleet3_3398563345700246': None, 'fleet5_3398563345700246': None, 'fleet7_3398563345700246': None, 'fleet9_3398563345700246': None, 'fleet11_3398563345700246': None, 'FleetName': {'type': 'army', 'uid': 1, 'name': 'FleetName', 'status': 4096, 'target': '', 'consumables': [], 'inventory': [], 'playerLevel': 20, 'specialBits': None, 'lost': None, 'lastUnitLost': None, 'lastIndexLost': None, 'allies': None, 'battleTarget': None, 'battleTimestamp': None, 'ransomRandom': None, 'ransomResource': None, 'ransomAmount': None, 'units': ['V04,,,,', 'U05,,,,', 'SU03,,,,', 'V62,,,,'], 'store': [0], 'fleets': [], 'upgrades': None, 'hp': None, 'invader': True}, 'fleet12_3398563345700246': ['UN33,780,0,0,0', 'UN33,780,0,1,0', 'UN06,740,0,2,0', 'UN06,740,0,3,0', 'V06,180,1,4,0']}
#


FIRST_QUESTS = [
    {'name': 'Q6016', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0},
    {'name': 'Q0531', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
    {'name': 'Q0516', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1}]
SECOND_QUESTS = [
    {'name': 'Q6019', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0},
    {'name': 'Q0633', 'complete': True, 'expired': False, 'progress': [1, 2, 1], 'completedTasks': 7},
    {'name': 'Q0676', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0},
    {'name': 'Q0521', 'complete': False, 'expired': False, 'progress': [0], 'completedTasks': 0},
    {'name': 'Q0691', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
    {'name': 'Q0671', 'complete': True, 'expired': False, 'progress': [2, 2], 'completedTasks': 3},
    {'name': 'Q0571', 'complete': True, 'expired': False, 'progress': [1, 1], 'completedTasks': 3},
    {'name': 'Q0591', 'complete': True, 'expired': False, 'progress': [4], 'completedTasks': 1},
    {'name': 'Q1098', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
    {'name': 'Q6011', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
    {'name': 'Q0611', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
    {'name': 'Q6016', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
    {'name': 'Q0531', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
    {'name': 'Q0516', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1}]


def fight_task(quest):
    [task] = [t for t in tasks(quest) if t.get('action') == 'fight']
    return task


def run_quest_battle(params, session_quests, quest):
    """A battle of a quest with no fleet of the player in the session: the units the task gives the player against
    the baddies of its fleet item (no research, no campaign island: their XML strengths)."""
    run_init_battle_dynamic(
        params,
        [lambda s: s.setdefault('quests', default=[dict(q) for q in session_quests]),
         lambda s: s.setdefault('user_object', default={'userInfo': {'world': {'research': {}}}})],
        task_fleet(fight_task(quest)), fight_baddies(fight_task(quest)), [], research={})


def test_init_battle_first_quest():
    run_quest_battle({'id': [0, 0], 'fleet': 'fleet1_2341959767162880', 'target': 'Q6016', 'ch': 3027, 'map': None},
                     FIRST_QUESTS, 'Q6016')


def test_init_battle_ai_first_quest():
    run_quest_battle({'fleet': 'fleet1_2341959767162880', 'target': 'Q6016', 'ch': 3028, 'map': None},
                     FIRST_QUESTS, 'Q6016')


def test_init_battle_second_quest():
    run_quest_battle({'id': [1, 0], 'fleet': 'fleet3_2341959767162880', 'target': 'Q6019', 'ch': 3069, 'map': None},
                     SECOND_QUESTS, 'Q6019')


def test_init_battle_ai_second_quest():
    run_quest_battle({'fleet': 'fleet3_2341959767162880', 'target': 'Q6019', 'ch': 3070, 'map': None},
                     SECOND_QUESTS, 'Q6019')


def test_init_battle_quest_fight_by_fleet_name():
    """QW228 is open: its fight task has fleetname="quest_W228_1_3" and no <fleet>, so the player fights with the
    fleet of the session against the baddies of its fleet item (BD30); a done quest of the list does not count."""
    task = fight_task('QW228')
    assert task.get('fleetname') == 'quest_W228_1_3' and task.find('fleet') is None
    own = ['U05,,,,', 'V61,,,,']
    run_init_battle_dynamic(
        {'fleet': 'fleet2_2341959767162880', 'target': 'quest_W228_1_3', 'ch': 1, 'map': None},
        [lambda s: s.setdefault('quests', default=[
            {'name': 'Q6016', 'complete': True, 'expired': False, 'progress': [1], 'completedTasks': 1},
            {'name': 'QW228', 'complete': False, 'expired': False, 'progress': [0, 0, 0], 'completedTasks': 0}]),
         lambda s: s.setdefault('fleets', default={'fleet2_2341959767162880': own}),
         lambda s: s.setdefault('user_object', default={'userInfo': {'world': {'research': {}}}})],
        codes_of(own), fight_baddies(task), [], research={})


def run_init_battle(params):
    with app.test_request_context():
        setup_session()

        friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables = \
            battle_engine.init_battle(params)

        assert_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)
        log_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)


def run_init_battle_invade(params):
    with app.test_request_context():
        setup_session_invade()

        friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables = \
            battle_engine.init_battle(params)

        assert_result_invade(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)
        log_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)


def run_init_battle_dynamic(params, setup_session_funcs, expected_friendly_codes, expected_baddie_codes,
                            expected_shielded, research, island=None):
    with app.test_request_context():
        for setup_session_func in setup_session_funcs:
            setup_session_func(session)

        friendlies, friendly_strengths, baddies, baddie_strengths, active_consumables = \
            battle_engine.init_battle(params)

        assert_dynamic_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths,
                              expected_friendly_codes, expected_baddie_codes, expected_shielded, research, island)
        log_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths)



def log_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths):
    print("friendlies", repr(friendlies))
    print("friendly_strengths", repr(friendly_strengths))
    print("baddies", repr(baddies))
    print("baddie_strengths", repr(baddie_strengths))
    print("active_consumables", repr(active_consumables))


def log_result_battle(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths, player_turn):
    print("friendly unit id", repr(friendlies))
    print("friendly_strengths", repr(friendly_strengths))
    print("baddy unit id", repr(baddies))
    print("baddie_strengths", repr(baddie_strengths))
    print("active_consumables", repr(active_consumables))
    print("player turn", repr(player_turn))


def assert_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths):
    assert_dynamic_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths,
                          codes_of(OWN_UNITS), codes_of_counts(ENEMY_FLEET), [], RESEARCH, ('C037', C037_ISLAND))


def assert_units(units, expected_codes):
    """The units are the game's items of these codes, in this order (code and unit type as in the XML)."""
    assert [u['-code'] for u in units] == expected_codes
    assert [u['unit']['-type'].split(',') for u in units] == [client.unit(c)['types'] for c in expected_codes]


def assert_dynamic_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths,
                          expected_friendly_codes, expected_baddie_codes, expected_shielded, research, island):
    """The player's units start with their researched strength (UnitItem.getStrength with the fleet), the enemy's
    with the strength of the campaign island if there is one (int(strength * mult)), else their XML strength; each
    unit with shields research has the shield power for the whole battle."""
    assert_units(friendlies, expected_friendly_codes)
    assert friendly_strengths == [researched_strength(c, research.get(c, [])) for c in expected_friendly_codes]
    assert_units(baddies, expected_baddie_codes)
    assert baddie_strengths == [island_strength(island[0], island[1], c) if island else client.strength(c)
                                for c in expected_baddie_codes]
    assert [(c['-code'], target) for c, target, _ in active_consumables] == \
        [(the_shield_power(), ('ally', i)) for i in expected_shielded]


def assert_result_invade(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths):
    own = codes_of(INVADE_OWN_UNITS)
    shielded = [i for i, code in enumerate(own) if has_shields_research(code, RESEARCH)]
    assert shielded == [0, 1]  # the two V06 have XR05 (shields 1)
    assert_dynamic_result(active_consumables, baddie_strengths, baddies, friendlies, friendly_strengths,
                          own, codes_of(INVADE_ENEMY_UNITS), shielded, RESEARCH, None)


def setup_session():
    session["fleets"] = {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None,
                         'fleet5_2341959767162880': None,
                         'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None,
                         'fleet11_2341959767162880': None,
                         'fleet13_2341959767162880': None,
                         'fleet15_2341959767162880': dict(ENEMY_FLEET),
                         'fleet14_2341959767162880': list(OWN_UNITS),
                         'ally_fleet14_2341959767162880': ['123']}
    setup_user_object()
    session.sid = "0"


def setup_session_invade():
    session["fleets"] = {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None,
                         'fleet5_2341959767162880': None,
                         'fleet7_2341959767162880': None, 'fleet9_2341959767162880': None,
                         'fleet11_2341959767162880': None,
                         'fleet13_2341959767162880': None,
                         'FleetName': {'type': 'army', 'uid': '6709797546928099', 'name': 'FleetName',
                                                      'status': 0, 'target': '',
                                                      'consumables': [], 'inventory': [], 'playerLevel': 1,
                                                      'specialBits': None, 'lost': None,
                                                      'lastUnitLost': None, 'lastIndexLost': None, 'allies': None,
                                                      'battleTarget': None,
                                                      'battleTimestamp': None, 'ransomRandom': None,
                                                      'ransomResource': None,
                                                      'ransomAmount': None,
                                                      'units': list(INVADE_ENEMY_UNITS),
                                                      'store': [0], 'fleets': [], 'upgrades': None, 'hp': None,
                                                      'invader': False},
                         'fleet14_2341959767162880': list(INVADE_OWN_UNITS)}

    setup_user_object()
    session.sid = "0"


def setup_user_object():
    session['user_object'] = {'userInfo': {'world': {'campaign': {'current': 'camp001', 'active': {
        'C000': {'status': 2097152, 'fleets': []}, 'C003': {'status': 5242880, 'fleets': []},
        'C004': {'status': 6291456, 'fleets': []}, 'C005': {'status': 7340032, 'fleets': []},
        'C006': {'status': 7340032, 'fleets': []}, 'C007': {'status': 5242880, 'fleets': []},
        'C008': {'status': 7340032, 'fleets': []}, 'C009': {'status': 7340032, 'fleets': []},
        'C010': {'status': 7340032, 'fleets': []}, 'C011': {'status': 8388608, 'fleets': []},
        'C012': {'status': 7340032, 'fleets': []}, 'C013': {'status': 7340032, 'fleets': []},
        'C014': {'status': 7340032, 'fleets': []}, 'C015': {'status': 8388608, 'fleets': []},
        'C016': {'status': 8388608, 'fleets': []}, 'C017': {'status': 9437184, 'fleets': []},
        'C018': {'status': 9437184, 'fleets': []}, 'C019': {'status': 9437184, 'fleets': []},
        'C020': {'status': 9437184, 'fleets': []}, 'C021': {'status': 8388608, 'fleets': []},
        'C022': {'status': 8388608, 'fleets': []}, 'C023': {'status': 8388608, 'fleets': []},
        'C024': {'status': 9437184, 'fleets': []}, 'C025': {'status': 8388608, 'fleets': []},
        'C026': {'status': 9437184, 'fleets': []}, 'C027': {'status': 9437184, 'fleets': []},
        'C028': {'status': 8388608, 'fleets': []}, 'C029': {'status': 9437184, 'fleets': []},
        'C030': {'status': 8388608, 'fleets': []}, 'C031': {'status': 8388608, 'fleets': []},
        'C032': {'status': 9437184, 'fleets': []}, 'C033': {'status': 9437184, 'fleets': []},
        'C034': {'status': 8388608, 'fleets': []}, 'C035': {'status': 9437184, 'fleets': []},
        'C036': {'status': 8388608, 'fleets': []}, 'C037': {'status': 2097152, 'fleets': []}}, 'mastery': {}}}}}
    session['user_object']["userInfo"]["world"]["research"] = {k: list(v) for k, v in RESEARCH.items()}


# --- powers on the enemy fleet of setup_session (U58, SU02, U63 on island 2 of C037) ------------------------------

def start_strengths():
    return [island_strength('C037', C037_ISLAND, c) for c in codes_of_counts(ENEMY_FLEET)]


def own_strengths():
    return [researched_strength(c, RESEARCH.get(c, [])) for c in codes_of(OWN_UNITS)]


def after_power(code, target, strengths):
    """A power on the target: its direct impact on it; with a chipFactor, ChipDamageManager.getDamage on each other
    unit that was alive before it, counted by the units alive before it (the target too, even when it dies)."""
    codes = codes_of_counts(ENEMY_FLEET)
    live = [i for i, s in enumerate(strengths) if s > 0]
    out = list(strengths)
    out[target] = max(out[target] - power_damage(code, codes[target]), 0)
    if items()[code].find('consumable').get('chipFactor'):
        for k, i in enumerate(live):
            if i != target:
                out[i] -= chip_damage(code, len(live), live.index(target), k)
    return out


def test_assign_consumable_response_consumable(monkeypatch):
    expected = after_power('N04', 1, start_strengths())
    assert expected == [120, 170, 150]  # an air strike of 30 (twice on land only) on the SU02 (200)
    run_assign_consumable_response(monkeypatch,
                                   {'id': 1, 'ch': 3207, 'level': 0, 'name': 'fleet15_2341959767162880', 'fleet': None,
                                    'map': 'C037', 'code': 'N04'}, None, own_strengths(), None, expected, [], True)


def test_assign_consumable_response_shrapnel(monkeypatch):
    expected = after_power('N80', 1, start_strengths())
    # 30 on the SU02; uniqueNumber(1, 0) = 4 and (1, 2) = 3 of 3 units: ceil(4 * 3 * 30 / 100) = 4, ceil(2.7) = 3
    assert UNIQUE_NUMBER[3][1] == [4, 0, 3] and expected == [116, 170, 147]
    run_assign_consumable_response(monkeypatch,
                                   {'id': 1, 'ch': 3207, 'level': 0, 'name': 'fleet15_2341959767162880',
                                    'fleet': None,
                                    'map': 'C037', 'code': 'N80'}, None, own_strengths(), None, expected, [],
                                   True)


def test_assign_consumable_response_shrapnel_removed_dead(monkeypatch):
    before = start_strengths()
    before[1] = 0  # the SU02 is dead: 2 units left, the U63 is the second of them
    expected = after_power('N80', 2, before)
    assert expected == [116, 0, 120]  # uniqueNumber(1, 0) of 2 units = 4: ceil(4 * 3 * 30 / 100) = 4
    run_assign_consumable_response(monkeypatch,
                                   {'id': 2, 'ch': 3207, 'level': 0, 'name': 'fleet15_2341959767162880',
                                    'fleet': None,
                                    'map': 'C037', 'code': 'N80'}, None, own_strengths(), None, expected, [],
                                   True,  setup_session_funcs= [lambda s: s.setdefault('battle', default=(own_strengths(), list(before), [], battle_engine.BattleContext()))])


def test_assign_consumable_response_shrapnel_unit_dead(monkeypatch):
    before = start_strengths()
    before[1] = power_damage('N80', 'SU02')  # the SU02 dies of the 30
    expected = after_power('N80', 1, before)
    assert expected == [116, 0, 147]
    run_assign_consumable_response(monkeypatch,
                                   {'id': 1, 'ch': 3207, 'level': 0, 'name': 'fleet15_2341959767162880',
                                    'fleet': None,
                                    'map': 'C037', 'code': 'N80'}, None, own_strengths(), None, expected, [],
                                   True,  setup_session_funcs= [lambda s: s.setdefault('battle', default=(own_strengths(), list(before), [], battle_engine.BattleContext()))])


def run_assign_consumable_response(monkeypatch, params, expected_player_unit_id, expected_friendly_strengths, expected_enemy_unit_id,
                          expected_baddie_strengths, expected_active_consumables, expected_player_turn, setup_session_funcs=[]):
    friendly_strengths = None
    baddie_strengths = None
    player_turn = None
    player_unit_id = None
    enemy_unit_id = None
    active_consumables = None

    def report_battle_log_mock(a, b, c, d, e, f):
        nonlocal friendly_strengths, baddie_strengths, player_turn, player_unit_id, enemy_unit_id, active_consumables
        (friendly_strengths, baddie_strengths, player_turn, player_unit_id, enemy_unit_id, active_consumables) = (a, b, c, d, e, f);

    monkeypatch.setattr(battle_engine, "report_battle_log", report_battle_log_mock)
    with app.test_request_context():
        setup_session()
        session['user_object']["userInfo"]["player"] = {"inventory": {"items" : {}}, "tutorialProgress": "tut_step_powerUpPowerUsed", "energy" : 35, "energyMax": 35, "lastEnergyCheck": 0} # free powerup
        # the power's hits pay like a unit's (battle_engine.consumable_hit_rewards)
        session['user_object']["userInfo"]["player"]["xp"] = 0
        session['user_object']["userInfo"]["world"].update(
            {"resources": {"coins": 0, "energy": 0, "oil": 0, "aluminum": 0, "copper": 0, "gold": 0, "iron": 0, "uranium": 0},
             "resourceOrder": ["aluminum", "copper", "gold", "iron", "uranium"], "rewardRandSeedW": 1, "rewardRandSeedZ": 1})
        session["quests"] = []
        for setup_session_func in setup_session_funcs:
            setup_session_func(session)
        battle_engine.assign_consumable_response(params)

        assert_battle_result(active_consumables, baddie_strengths, enemy_unit_id, player_unit_id, friendly_strengths, player_turn, expected_friendly_strengths, expected_enemy_unit_id, expected_player_unit_id,
                          expected_baddie_strengths, expected_active_consumables, expected_player_turn)
        log_result_battle(active_consumables, baddie_strengths, enemy_unit_id, player_unit_id, friendly_strengths, player_turn)


def assert_battle_result(active_consumables, baddie_strengths, enemy_unit_id, player_unit_id, friendly_strengths, player_turn,
                          expected_friendly_strengths, expected_enemy_unit_id, expected_player_unit_id,
                          expected_baddie_strengths, expected_active_consumables, expected_player_turn):
    assert player_unit_id == expected_player_unit_id
    assert friendly_strengths == expected_friendly_strengths
    assert enemy_unit_id == expected_enemy_unit_id
    assert baddie_strengths == expected_baddie_strengths
    assert active_consumables == expected_active_consumables
    assert player_turn == expected_player_turn


def test_spawn_fleet_initial_attack():
    """Q6019's fight task is a PVE invasion (isPVE): the client is told where it lands and who leads it."""
    task = fight_task('Q6019')
    with app.test_request_context():
        session["fleets"] = {}

        res = battle_engine.spawn_fleet({'fleet': 'Q6019', 'code': 'Q6019'})

        assert res == {'errorType': 0, 'userId': 1,
         'metadata': {'newPVE': {'status': 2, 'pos': task.get('spawnLocation'), 'villain': task.get('pveVillain'),
                                 'quest': 'Q6019'}}, 'data': []}
        assert session["fleets"] == {}


def test_spawn_fleet_quest_based():
    with app.test_request_context():
        session["fleets"] = {}
        session.sid = "0"

        res = battle_engine.spawn_fleet({'fleet': 'quest_W228_1_3', 'code': 'QW228'})

        assert res == {'errorType': 0, 'userId': 1, 'metadata': {}, 'data': []}
        assert session["fleets"] == {'fleet1_2341959767162880': None}


def test_spawn_fleet_quest_odd_fleets():
    with app.test_request_context():
        session["fleets"] = {'fleet1_2341959767162880': None}
        session.sid = "0"

        res = battle_engine.spawn_fleet({'fleet': 'BD_QW246_01_3', 'code': 'QW246'})

        assert res == {'errorType': 0, 'userId': 1, 'metadata': {}, 'data': []}
        assert session["fleets"] == {'fleet1_2341959767162880': None, 'fleet3_2341959767162880': None}


def test_decode_unit_count_list():
    res = battle_engine.decode_unit_count_list([
        {
            "-U43": "2",
            "-PCK": "1"
        },
        {"-U43": "2"}
    ])
    assert res == ["U43", "U43", "PCK", "U43", "U43"]


def test_encode_unit_string():
    res = battle_engine.encode_unit_string("U43")
    assert res == 'U43,,,,'


def test_encode_unit_string_with_hp_shields():
    res = battle_engine.encode_unit_string("U43", hp=40, shield=1)
    assert res == 'U43,40,1,,'



def test_encode_unit_strings():
    res = battle_engine.encode_unit_strings(["U43", "U43", "PCK", "U43", "U43"])
    assert res == ["U43,,,,", "U43,,,,", "PCK,,,,", "U43,,,,", "U43,,,,"]


def test_decode_unit_string():
    res = battle_engine.decode_unit_string('U43,1,2,3,4')
    assert res == 'U43'


def test_decode_unit_strings():
    res = battle_engine.decode_unit_strings(["U43,,,,", "U43,,,,", "PCK,,,,", "U43,,,,", "U43,,,,"])
    assert res == ["U43", "U43", "PCK", "U43", "U43"]



def test_get_survival_player_fleet():

    with app.test_request_context():

        setup_session_invade()
        session['user_object']["userInfo"]["player"] = {"level": 7}  # the fleet gets it

        session["last_battle"] = ([10, 11, 12, 13, 14], [], [({'-name': 'consumable75', '-type': 'consumable', '-subtype': 'consumable',
                             '-storable': 'true', '-buyable': 'true', '-code': 'N75', '-version': '2',
                             'requiredLevel': '10', 'cost': {'-cash': '30'}, 'tooltip': {'-type': 'consumable'},
                             'consumable': {'-duration': '0', '-energy': '0', '-type': 'all',
                                            '-diweapon': 'DefenseShield', '-postWait': '1s',
                                            '-givesAbility': 'shield'}, 'image': [
                                  {'-name': 'icon',
                                   '-url': 'assets/game/consumables/ConsumablesUI.swf/Shield_01_96.png'},
                                  {'-name': 'cursor',
                                   '-url': 'assets/game/consumables/ConsumablesUI.swf/Shield_01_49.png'}],
                             'loc': {'-sentenceName': 'true'},
                             'requiredExperiment': {'-name': 'empires_consumable_2', '-variants': '3'}}, ('ally', 2), 999999)])

        res = battle_engine.get_survival_player_fleet()

        assert res == {
            "type": "army",
            "uid": 2341959767162880,
            "name": "fleet14_2341959767162880",
            "status": 2048,  # survival player
            "target": "",
            "consumables": [],
            "inventory": [],
            "playerLevel": 7,
            "specialBits": None,
            "lost": None,
            "lastUnitLost": None,
            "lastIndexLost": None,
            "allies": None,
            "battleTarget": None,
            "battleTimestamp": None,
            "ransomRandom": None,
            "ransomResource": None,
            "ransomAmount": None,
            "units": ['V06,10,0,,', 'V06,11,0,,', 'UN33,12,1,,', 'UN33,13,0,,', 'UL61,14,0,,'],
            "store": [0],  # [0, 0, 0],
            "fleets": [],
            "upgrades": {'V06': "XD05,XT05,XA05,XC05,XR05,XS05"},
            "hp": None,
            "invader": False
        }
