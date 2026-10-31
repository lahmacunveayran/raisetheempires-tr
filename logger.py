import functools
import json
import traceback

from flask_socketio import SocketIO

from game_settings import game_settings
from quest_settings import quest_settings


socketio = SocketIO()


def never_fails(report):
    """Logging for the log page must never fail the call it reports on."""
    @functools.wraps(report)
    def wrapper(*args, **kwargs):
        try:
            return report(*args, **kwargs)
        except Exception:
            print("Could not report to the log page:")
            traceback.print_exc()
    return wrapper


@never_fails
def report_tutorial_step(step, response, new_pve, sequence, endpoint):
    quest_names = [r['name'] for r in response] if response else []
    quests = [r for r in quest_settings['quests']['quest'] if r['_name'] in quest_names]
    socketio.emit('tutorial_step', [step, response, new_pve, describe_step(step), quests, sequence, endpoint])


def describe_step(step):
    [descr] = [e for e in game_settings['settings']['tutorial']['step'] if e['-id'] == step]
    return descr


@never_fails
def report_world_log(operation, response, req, sequence, endpoint, response2, new_pve):
    quest_names = [r['name'] for r in response2] if response2 else []
    quests = [r for r in quest_settings['quests']['quest'] if r['_name'] in quest_names]
    req2 = json.loads(json.dumps(req, default=lambda o: '<not serializable>'))
    res = (response[0] if response else {}) if isinstance(response, list) else response
    socketio.emit('world_log', [operation, res.get("id", "response") if isinstance(res, dict) else res, req2, sequence, endpoint, response2, new_pve, quests, response])


@never_fails
def report_other_log(service, response, req, endpoint):
    req2 = json.loads(json.dumps(req, default=lambda o: '<not serializable>'))
    socketio.emit('other_log', [service, response, req2, req.sequence, endpoint])


@never_fails
def report_battle_log(friendly_strengths, baddie_strengths, player_turn, player_unit_id, enemy_unit_id, active_consumables):
    friendly_strengths_ = [str(s) for s in friendly_strengths]
    baddie_strengths_ = [str(s) for s in baddie_strengths]
    if player_unit_id is not None:
        mark_array_element(friendly_strengths_, player_unit_id)
    if enemy_unit_id is not None:
        mark_array_element(baddie_strengths_, enemy_unit_id)
    for consumable, consumable_target, tries in active_consumables:
        if consumable_target[1] is None:
            for i in range(len(baddie_strengths_ if consumable_target[0] == "enemy" else friendly_strengths_)):
                mark_consumable_array_element(baddie_strengths_ if consumable_target[0] == "enemy" else friendly_strengths_, i, tries)
        else:
            mark_consumable_array_element(baddie_strengths_ if consumable_target[0] == "enemy" else friendly_strengths_, consumable_target[1], tries)

    socketio.emit('battle_log', ', '.join(friendly_strengths_) + (' => ' if player_turn else ' <= ') + ', '.join(baddie_strengths_))


def mark_array_element(strengths, unit_id):
    strengths[unit_id] = "[" + strengths[unit_id] + "]"


def mark_consumable_array_element(strengths, unit_id, tries):
    superscript = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    strengths[unit_id] = strengths[unit_id] + "💣" + str(tries).translate(superscript)
