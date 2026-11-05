"""Classification of the surviving mutants of mut_harness.py (denetim2): E = equivalent (cannot change any observable
behaviour; the proof is given), G = real gap of the tests. The judgments are the auditor's; the script checks that
every survivor of every result file is classified and gives the score with the equivalent mutants left out.
Usage: python mut_survivors.py   (in this folder)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E, G = "E", "G"
PRINT = (E, "only a print() argument changes; prints are not part of the answer or the save")

CLASS = {
    "mut_battle_engine.json": {
        "3": (G, "meta key newPVE: the answer's metadata of battle_complete_response is not asserted"),
        "4": (G, "meta newPVE 0->1: the client reads newPVE; not asserted"),
        "18": (G, "ally target of accuracy/evasion/shield consumables: no test with ally consumables in a turn"),
        "34": (E, "init_seed is only used in print() (lines 123, 139)"),
        "44": (G, "sign of the consumable accuracy: accuracy is always 0 in the turn tests"),
        "129": PRINT,
        "142": (G, "damage > 0 -> > 1: rewards of a 1-damage hit not asserted"),
        "144": (G, "quest progress name battleDamage: progress not asserted"),
        "203": (G, "DoT on all enemies: no DoT test (apply_dot_damage never runs)"),
        "218": (G, "DoT targeting of allies: no DoT test"),
        "226": (G, "consumable duration tries-2: remaining consumable turns not asserted"),
        "286": (G, "replay reward boundary a == combatReplayRewardMinimum (100) not tested"),
        "292": (G, "item rewards when replaying: replay path with item rewards not tested"),
        "354": (G, "invader (FleetName) win branch of handle_win not tested"),
        "553": PRINT,
        "689": (G, "open-quest filter of init_battle: the fallback gives the same enemies, the friendlies source is not told apart"),
        "691": (E, "task = '' vs None: only read by `if not task` (falsy both) before it is set"),
        "733": (E, "battle tuples are only ever made at 513, 521, 696 (None,None,None,ctx) and server 2959 (list,None,list,ctx);"
                   " no state has [0] and [2] None with [1] set, so [1] is None adds nothing"),
        "786": (E, "get_last_fleet_name: with i=0 the second clause of the while is 'fleet1_'+zid, the same test as the"
                   " first; the first value is overwritten in the loop"),
        "864": (E, "default '' -> 'XXXX' of a missing -poor: no unit type is called XXXX"),
        "1012": (G, "campaign mastery (has_battle_context path) not tested"),
        "1050": (G, "get_min_island_mastery_from_battle / replay not tested"),
        "1051": (G, "replay mastery not tested"),
        "1054": (G, "replay mastery not tested"),
        "1257": (E, "targeted False -> None: only read by `if targeted` and `targeted and ...` (falsy both)"),
        "1298": (G, "ally (A0A) power selection may pick secondary powers: list of valid ally powers not asserted"),
        "1310": (E, "the clause c['-target'] == 'enemy' is written twice in the production code; the mutant changes the copy"),
        "1364": (E, "'AI tried' markers: every read of active_consumables matches the target first (is_stunned 1170,"
                    " get_consumable_int 1200, is_affected 1177, end turn 173-185 'enemy'/'ally', shield 1473/1478 .get);"
                    " target[0]=='AI tried' never matches, so the dict is never read"),
        "1379": PRINT,
        "1392": (G, "type 'all' consumables (whole-side powers) not tested"),
        "1427": (G, "random ally target with one live ally (ally power, not enemy turn) not tested"),
        "1430": (G, "target of ally-side powers (heal/buff duration) not asserted"),
        "1478": (G, "AI cast marker: the AI's second (targeted) assign after a cast is not tested (line 965 reads it)"),
        "1486": (G, "metadata key of assign_consumable_response not asserted"),
        "1508": (G, "shield with a 0-damage power not tested"),
        "1509": (G, "shield with a 1-damage power not tested"),
        "1517": (G, "power on a dead unit (0 strength) not tested"),
        "1520": (G, "secondary type-all powers with -percent not tested"),
        "1523": (G, "secondary type-all powers with -percent not tested"),
        "1557": PRINT,
        "1567": PRINT,
        "1571": PRINT,
        "1596": (E, "default of -di: all 4 consumables with -chipFactor in gameSettings_with_fixes.xml have di"),
        "1621": PRINT,
        "1624": (E, "<= 0 -> < 0: at exactly 0 the block only sets 0 again and prints"),
        "1625": (G, "collateral damage leaving an ally at 1 strength not tested"),
        "1654": (E, "diagonal of the adjacency table: unit_1 == unit_2 returns 0 at line 1149 before the table"),
        "1658": (E, "diagonal of the adjacency table, as 1654"),
        "1732": (G, "evasion (-defend) consumables not tested"),
        "1903": (G, "campaign 02 ('D' maps) not tested"),
        "1906": (G, "campaign 02 ('D' maps) not tested"),
        "2092": PRINT,
        "2117": (G, "loss reward of a unit whose cost has -rare: only one rare kind tested"),
        "2122": (G, "loss reward of -nrare1 not tested"),
        "2127": (G, "loss reward of -nrare4 not tested"),
        "2150": PRINT,
        "2153": PRINT,
        "2180": (G, "has_battle_context always False -> mastery/replay never run: not detected"),
        "2194": (G, "BattleContext.map_name default: campaign context not asserted"),
    },
    "mut_save_engine.json": {
        "0": (G, "crash_log default True: the tests turn it off (conftest) and nothing checks the default"),
        "1": (G, "crash_log default, as 0"),
        **{k: (G, "lookup_objects_by_item_name: not used by the save tests") for k in ("17", "18", "19", "20", "21", "22")},
        "40": (G, "CIRCULAR: empires_test.py:414-420 takes the expected count from backup_db.MAX_BACKUPS itself"),
        **{k: (G, "BACKUP_KEYS: the content of a restored backup (quests, battle, fleets, population, saved,"
                  " saved_on, original_save_version) is not asserted") for k in ("43", "44", "45", "46", "47", "48", "50")},
        "58": (G, "_save_id of saves read from the database (session_id key) not tested"),
        "59": (G, "_save_id fallback 'local' not tested"),
        "62": (G, "_save_id prefix cut: store and list use the same function, so a wrong cut is consistent; not tested"
                  " against the real session id"),
        "63": (G, "_save_id of a save read from the database (prefix 'session:') not compared with create_backup's id"),
        "66": (G, "saved_on column of a backup not asserted"),
        "67": (G, "replaced_on column of a backup not asserted"),
        "70": (G, "default message of a backup without message (nested chain) not asserted"),
        **{k: (G, "list_backups metadata (saved_on, replaced_on, save_version) not asserted")
           for k in ("78", "79", "80", "81", "82", "83")},
        "95": (G, "nested chain: a stored backup still holding its own chain is not detected"),
        "101": (G, "backup timestamps not asserted"),
        "102": (E, "deepcopy -> copy: store_backup pickles the backup at once (line 83), before the session can change"),
        "105": (G, "replaced_on of create_backup not asserted"),
        "106": (G, "replaced_on of create_backup not asserted"),
        "109": (G, "session saved_on after create_backup not asserted"),
        "110": (G, "session saved_on after create_backup not asserted"),
        "111": (G, "save_database_uri: the tests set their own database URI, the real one is never checked"),
        "113": (G, "save_database_uri: running-from-source path not tested"),
        "114": (G, "save_database_uri: running-from-source path not tested"),
        "124": (G, "save_database_uri: running-from-source path not tested"),
        "125": PRINT,
        "126": PRINT,
        "127": (G, "save_database_uri: the returned URI is never checked"),
        "132": (G, "base_path of the frozen exe not tested"),
        "136": (G, "set_crash_log(True) not tested (the tests only call it with False)"),
        "142": (G, "name of the log file (the 500 handler opens log.txt) not checked"),
        "143": (G, "exception_handler (uses logger) not tested"),
        "153": (G, "get_saves with a save without user_object not tested"),
        "155": (G, "enrich_save session_id not asserted"),
        "161": (E, "pending_saves left in g: guarded_call (empires-server.py:988) sets a new list for every call and no"
                   " store_session runs after the block in the same request [inferred]"),
        "168": (E, "converted is only printed; with 1 at the start a no-op commit is added"),
        "175": (E, "converted is only printed and tested for != 0, which holds for 1 as for n >= 1"),
        "176": (E, "converted -n is != 0 too; only the print changes"),
        "177": (E, "converted 2n: only the print changes"),
        "179": PRINT,
        "180": PRINT,
        "181": (G, "validate_save default: a save without user_object must be refused; not tested"),
        "202": (G, "validate_save: level int AND the others -> OR; a save with a good level and a bad other field is"
                   " not tested (the mutant is on line 286, the statement starts there)"),
        "203": (G, "validate_save blank_allowed path not tested"),
        "204": (G, "validate_save blank_allowed path not tested"),
        "205": (G, "validate_save blank_allowed path not tested"),
    },
    "mut_server_save.json": {
        **{k: (G, "ASSET_PATH_PREFIXES: only some asset paths are tested to skip the save (and its lock)")
           for k in ("1", "2", "4", "6", "7", "8")},
        "32": PRINT,
        "44": (G, "SESSION_COOKIE_HTTPONLY: cookie flag not asserted"),
        "45": (E, "HTTPONLY None: werkzeug set_cookie adds HttpOnly only `if httponly`, None and False give the same cookie"),
        "52": (G, "MAX_FORM_MEMORY_SIZE (5 MB save editor form) not tested"),
        "55": (G, "MAX_FORM_MEMORY_SIZE not tested"),
        **{k: (G, "SECURITY: cross-site block tested for /wipe_session and /save-editor only (empires_test.py:378-382);"
                  " /gazillionaire, /deprogress, /complete_quest/, /chooseavatar/ ... not") for k in ("60", "61", "65", "68")},
        "86": (E, "no HTTP_HOST and no SERVER_NAME: '' and 'XXXX' are both refused by is_known_host"),
        "93": (G, "content type of the 403 answer not asserted (cosmetic)"),
        "97": PRINT,
        "98": (G, "body of the 403 answer not asserted (cosmetic)"),
        "107": PRINT,
        "109": (G, "body of the 403 answer not asserted (cosmetic)"),
        "113": (G, "POST /wipe_session not tested"),
        "118": (G, "redirect target of /wipe_session not asserted (status only)"),
        "126": PRINT,
        **{k: (G, "save editor page: quest lists not asserted") for k in ("131", "133", "134")},
        **{k: (G, "save editor page: the save JSON shown (profilePic, battle, last_battle, fleets, population,"
                  " save_version) not asserted") for k in ("143", "151", "155", "159", "164", "172")},
        "178": (G, "save editor page: value that can't be shown not tested"),
        "182": (G, "save editor page: valid flag not asserted"),
        "191": PRINT,
        "193": (G, "save editor: restoring a backup (form key restore<n>) not tested by the save tests"),
        "217": (G, "save editor: backup message 'before <message>' not asserted"),
        "218": (G, "save editor: backup message not asserted"),
        **{k: (G, "save editor: session['saved'] marker not asserted") for k in ("229", "230", "233")},
        **{k: (G, "save editor: profilePic handling not tested") for k in ("238", "239", "241")},
        **{k: (G, "save editor: battle/fleets/population written by the editor not asserted")
           for k in ("248", "250", "253", "255")},
        "288": PRINT,
        "299": (G, "Ruffle gateway route /127.0.0.1flashservices/gateway.php not tested"),
        "301": (G, "transactional_session removed: no test of a request failing outside guarded_call (e.g. a broken AMF"
                   " body) restoring the save"),
        "302": PRINT,
        "326": (E, "logger=True/False of pyamf remoting.encode only changes logging, not the bytes"),
        "340": PRINT,
        "350": (G, "'data' key of the CALL_FAILED answer not asserted"),
        "351": (G, "500 handler registration: the tests call server_error_page() directly (session_layer_test.py:527),"
                   " no real failing request goes through it"),
        "352": (G, "500 handler registration, as 351"),
        "357": (G, "file name the crash editor opens not asserted"),
        "361": (E, "crash_log_editor '' vs None: only read by `crash_log_editor and ...is_alive()` (falsy both)"),
    },
    "mut_save_migration.json": {
        "0": PRINT,
        "7": (G, "0.02a step: only quests not complete are reset; not asserted"),
        "12": PRINT,
        **{k: (G, "0.02a step: the reset expansion list is not asserted (only the unlocked ones)")
           for k in ("23", "24", "26", "28", "30", "34", "37")},
        "63": (G, "no test migrates a 0.04a save (the step is skipped and the save stays 0.04a)"),
        "64": (G, "no test migrates a 0.04a save"),
        "116": (G, "0.06a -> 0.07a step: save_version not asserted"),
        **{k: (G, "0.08a step: the experiment values it sets are not asserted")
           for k in ("126", "127", "131", "133", "136", "137", "142", "152", "153", "156", "157", "166", "167", "171",
                     "181", "182", "183")},
        "198": (G, "0.02a step: zero_yield of quest progress not asserted"),
        "199": (G, "0.02a step: zero_yield of quest progress not asserted"),
    },
}


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5
    return (c - r) / d, (c + r) / d


def main():
    total = {"n": 0, "k": 0, "k2": 0, "e": 0, "g": 0}
    for fname, classes in CLASS.items():
        path = os.path.join(HERE, fname)
        if not os.path.exists(path):
            print(fname, "missing")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        res, meta = data["results"], data["meta"]
        surv = {k for k, r in res.items() if r["status"] == "survived"}
        missing = sorted(surv - set(classes), key=int)
        extra = sorted(set(classes) - surv, key=int)
        if missing or extra:
            print(fname, "unclassified:", missing, "not survivors:", extra)
            sys.exit(1)
        rechecked = all("full_status" in res[k] for k in surv)
        k2 = {k for k in surv if res[k].get("full_status") in ("killed", "error", "timeout")}
        left = surv - k2
        e = sum(1 for k in left if classes[k][0] == E)
        e_k2 = sum(1 for k in k2 if classes[k][0] == E)
        g = len(left) - e
        n = len(res)
        k = n - len(surv)
        print("%-26s sampled %d: killed by the file's tests %d (%.1f%%); survivors %d, of which killed by the whole"
              " suite %d%s; left %d = equivalent %d + gaps %d" % (fname, n, k, 100 * k / n, len(surv), len(k2),
              "" if rechecked else " (RECHECK NOT DONE)", len(left), e, g))
        kk, nn = k + len(k2), n - e
        lo, hi = wilson(kk, nn)
        share = meta["on_covered_lines"] / meta["total_mutants"]
        print("%-26s score, whole suite, equivalents left out: %d/%d = %.1f%% (95%% CI %.1f-%.1f%%); scope %d mutants,"
              " %d on run lines; estimate over the whole scope %.1f%% (CI %.1f-%.1f%%)"
              % ("", kk, nn, 100 * kk / nn, 100 * lo, 100 * hi, meta["total_mutants"], meta["on_covered_lines"],
                 100 * kk / nn * share, 100 * lo * share, 100 * hi * share))
        if e_k2:
            print("   note: %d mutants classified E were killed by the whole suite (check the proof)" % e_k2)
        for name, v in (("n", n), ("k", k), ("k2", len(k2)), ("e", e), ("g", g)):
            total[name] += v
        if "--list" in sys.argv:
            for key in sorted(surv, key=lambda s: res[s]["line"]):
                tag = "K2" if key in k2 else classes[key][0]
                print("   %-2s line %4d  %s" % (tag, res[key]["line"], classes[key][1]))
    print("ALL: sampled %d, killed %d + %d by the whole suite, equivalent %d, gaps %d -> %.1f%%"
          % (total["n"], total["k"], total["k2"], total["e"], total["g"],
             100 * (total["k"] + total["k2"]) / (total["n"] - total["e"])))


if __name__ == "__main__":
    main()
