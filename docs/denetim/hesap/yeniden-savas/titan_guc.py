"""Titan hasari: asil motor (battle_complete_response) ile istemci formulu, butun Titan birimleri ve bes seviye.

Istemci BattleAI.GetAttackingDamage:
    A = saldiranin UnitItem.getAttackStrength(fleet)      (Titan: strengths/entry[playerLevel < level].attackStrength)
    D = savunanin o anki gucu (unit.strength)
    hasar = 25 * (3A + D) / (3D + A) / 100 * savunanin getAttackStrength(fleet); 3 basamaga kesilir; carpan; ceil.
UnitItem.getXmlStrength seviyeyi fleet.playerLevel'dan okur. Bu betik iki durumu dener:
  1. filo seviyesi = oyuncu seviyesi (istemcinin kendi kurdugu filolar: Fleet(null) -> ZGlobal.player.level,
     Titan Lab'in BM03 filosu BattleMechlab.createEnemyFleet -> createFleet)
  2. dusman filosu seviyesi 1 (sunucunun komsu/PvP filolarina yazdigi "playerLevel": 1)
Kullanim (depo kokunden): ../venv312/Scripts/python.exe docs/denetim/hesap/yeniden-savas/titan_guc.py
"""
import contextlib
import io
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "test"))
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import battle_turn_test as T
    import battle_engine
    from game_settings import game_settings
    from quest_engine import simple_list


class Patch:
    def setattr(self, obj, name, value):
        setattr(obj, name, value)


def entry(code, level, attr):
    u = battle_engine.lookup_item_by_code(code)["unit"]
    if "-strength" in u:
        return int(u["-strength"])
    for e in simple_list(u["strengths"]["entry"]):  # getXmlStrength: the first entry with playerLevel < level
        if level < int(e["-level"]):
            return int(e[attr])
    return 1  # getXmlStrength: "no strength defined", returns 1


def kind(code):
    return battle_engine.lookup_item_by_code(code)["unit"]["-type"].split(",")[0]


def client_hit(att, att_level, dfn, dfn_level, d_left, r):
    a = entry(att, att_level, "-attackStrength")
    mult = entry(dfn, dfn_level, "-attackStrength")
    dmg = 25 * (3 * a + d_left) / (3 * d_left + a) / 100 * mult
    dmg = math.floor(dmg * 1000) / 1000
    crit, direct = battle_engine.get_hit_value(kind(att), kind(dfn))
    dmg *= 0.10 if r < direct else 1.5 if r >= crit else 1
    return math.ceil(dmg)


titans = [i["-code"] for i in game_settings["settings"]["items"]["item"]
          if isinstance(i.get("unit"), dict) and "strengths" in i["unit"] and "-strength" not in i["unit"]]
OTHER = "U01"  # antitank, 30
same = diff_enemy_level1 = total = 0
example = None
with T.app.test_request_context(), contextlib.redirect_stdout(io.StringIO()):
    for code in titans:
        for level in (15, 25, 35, 45, 55):
            for player_turn in (True, False):
                players, enemies = ([code], [OTHER]) if player_turn else ([OTHER], [code])
                T.setup(Patch(), players, enemies, level=level)
                crit, direct = battle_engine.get_hit_value(kind(players[0] if player_turn else enemies[0]),
                                                          kind(enemies[0] if player_turn else players[0]))
                r = direct
                T.fixed_rolls(Patch(), r)
                params = dict(T.PARAMS, id=[0, 0]) if player_turn else dict(T.PARAMS)
                before = None
                friendlies, fs, baddies, bs, _ = battle_engine.init_battle(T.PARAMS)
                before = (list(fs), list(bs))
                data = battle_engine.battle_complete_response(params)["data"]
                if player_turn:
                    server = before[1][0] - data["es"]
                    client = client_hit(code, level, OTHER, level, before[1][0], r)
                    client_l1 = client  # the player's own fleet has the player's level
                else:
                    server = before[0][0] - data["ps"]
                    client = client_hit(code, level, OTHER, level, before[0][0], r)
                    client_l1 = client_hit(code, 1, OTHER, level, before[0][0], r)
                # the enemy leaves 1 strength at most: compare what the engine applied with the clamp
                total += 1
                if server == client or (player_turn and before[1][0] - client <= 1 and data["es"] == 0):
                    same += 1
                elif example is None:
                    example = (code, level, player_turn, server, client)
                if not player_turn and client_l1 != server:
                    diff_enemy_level1 += 1
print("Titan birimi:", len(titans), "| denenen vurus:", total, "| motor = istemci (filo seviyesi = oyuncu seviyesi):",
      same)
print("ilk ayrilik:", example)
print("dusman Titan, istemci filo seviyesi 1 alirsa (komsu/PvP filolari) farkli hasar veren vurus:",
      diff_enemy_level1, "/", total // 2)
