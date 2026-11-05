"""Hand-made mutants for the behaviours the new tests guard (fail-to-pass): each is one text replacement that must occur
exactly once in the file; the named tests run against it (with a timeout) and must fail; the file is written back.
Only writes into the worktree given. Usage: python targeted.py --wt <worktree> --out <jsonl>"""
import argparse
import json
import os
import subprocess
import time

PY = r"C:\Users\<user>\Desktop\Raise\venv312\Scripts\python.exe"
LAUNCHER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_pytest_kayit_mut.py")
SRV = "test/save_server_test.py"
BAK = "test/save_backup_test.py"
MIG = "test/save_migration_test.py"
EMP = "test/empires_test.py"
PREFIXES = ['"/wipe_session"', '"/list_session"', '"/gazillionaire"', '"/deprogress"', '"/seed/"', '"/patch/"',
            '"/unlock_quest/"', '"/complete_quest/"', '"/remove_quest/"', '"/save-editor"', '"/chooseavatar/"',
            '"/login.html"', '"/new.html"']
PREFIX_LINE = ('SAVE_CHANGING_PATH_PREFIXES = ("/wipe_session", "/list_session", "/gazillionaire", "/deprogress", '
               '"/seed/", "/patch/",\r\n                               "/unlock_quest/", "/complete_quest/", '
               '"/remove_quest/", "/save-editor",\r\n                               "/chooseavatar/", "/login.html", '
               '"/new.html")')

MUTANTS = [
    # B-O6: each prefix of the cross-site guard left out
] + [("empires-server.py", PREFIX_LINE, PREFIX_LINE.replace(p, '"/x-left-out"'),
      [SRV + "::test_cross_site_requests_change_nothing"], "prefix %s left out of the cross-site guard" % p)
     for p in PREFIXES] + [
    ("empires-server.py", 'source = request.headers.get("Origin") or request.headers.get("Referer")',
     'source = request.headers.get("Referer")', [SRV + "::test_cross_site_requests_change_nothing"],
     "Origin header not checked"),
    # B-O7: save editor and backups
    ("empires-server.py", "if 'profilePic' in session and 'profilePic' in save_game :",
     "if 'profilePic' in save_game :",
     [SRV + "::test_the_save_editor_does_not_give_an_avatar_to_a_save_without_one"],
     "avatar taken from the edit without the save having one"),
    ("empires-server.py", "    session['population'] = save_game.get('population')\r\n", "",
     [SRV + "::test_the_save_editor_writes_what_it_was_given"], "editor does not write population"),
    ("empires-server.py", "save_game = load_backup(session, backup_ids[restores[0]])",
     "save_game = load_backup(session, backup_ids[0])",
     [SRV + "::test_a_backup_restored_in_the_save_editor_brings_the_save_back"], "restore<n> restores the newest"),
    ("empires-server.py", "if restores[0] >= len(backup_ids):", "if restores[0] > len(backup_ids):",
     [SRV + "::test_restoring_a_backup_that_is_not_there_changes_nothing"], "restore one past the end"),
    ("empires-server.py", "'battle': session['battle'] if 'battle' in session else None,",
     "'battle': session['fleets'] if 'battle' in session else None,",
     [SRV + "::test_the_save_editor_shows_every_part_of_the_save"], "editor page shows the wrong part"),
    ("empires-server.py", "response = make_response(redirect('/login.html'))",
     "response = make_response(redirect('/home.html'))",
     [SRV + "::test_deleting_the_save_backs_it_up_and_goes_to_the_login_page"], "wipe goes to the wrong page"),
    ("empires-server.py", "valid=validate_save(session, False),", "valid=validate_save(session, True),",
     [SRV + "::test_the_save_editor_says_when_the_save_is_corrupt"], "no save at all shown as valid"),
    ("empires-server.py", 'session[\'saved\'] = str(session.get(\'saved\', "")) + "edit"',
     'session[\'saved\'] = str(session.get(\'saved\', "XXXX")) + "edit"',
     [SRV + "::test_an_edit_without_an_avatar_keeps_the_saves"], "edit mark starts from something"),
    ("save_engine.py", "MAX_BACKUPS = 20", "MAX_BACKUPS = 21",
     [EMP + "::test_create_backup_keeps_save_small_and_bounded", BAK + "::test_twenty_backups_are_kept_per_save"],
     "21 backups kept"),
    ("save_engine.py", "backup['replaced_on'] = timestamp", "backup['replaced_on'] = timestamp + 1",
     [BAK + "::test_a_backup_holds_the_save_with_its_dates"], "replaced_on off"),
    ("save_engine.py", "    session['saved_on'] = timestamp\r\n", "",
     [BAK + "::test_each_backup_covers_the_time_from_the_one_before"], "saved_on of the save not moved on"),
    ("save_engine.py", "'original_save_version']", "]", [BAK + "::test_a_backup_holds_the_save_with_its_dates"],
     "original_save_version not backed up"),
    ("save_engine.py", 'return sid[len("session:"):] if sid.startswith("session:") else sid',
     'return sid.replace("session:", "")', [BAK + "::test_the_id_backups_are_kept_under"], "prefix cut anywhere"),
    ("save_engine.py", "(blank_allowed and 'user_object' not in save)", "(blank_allowed)",
     [BAK + "::test_one_wrong_field_makes_the_save_invalid"], "blank_allowed accepts any save"),
    ("save_engine.py", "isinstance(player.get(\"level\"), int) and", "isinstance(player.get(\"level\"), int) or",
     [BAK + "::test_one_wrong_field_makes_the_save_invalid"], "level alone makes a save valid"),
    # B-O4: save.db move
    ("save_engine.py", "shutil.move(save_db_path, new_save_db_path)", "shutil.copy(save_db_path, new_save_db_path)",
     [BAK + "::test_an_old_save_db_is_moved_to_the_instance_folder"], "old save.db left behind"),
    ("save_engine.py", "            if not os.path.exists(new_save_db_path):", "            if True:",
     [BAK + "::test_a_save_db_in_the_instance_folder_is_never_written_over"], "instance save.db written over"),
    ("save_engine.py", "shutil.copy(save_db_path, backup_save_dir_path)", "pass",
     [BAK + "::test_an_old_save_db_is_moved_to_the_instance_folder"], "no backup copy of save.db"),
    ("save_engine.py", "if os.path.samefile(my_games_path(), root_path):", "if True:",
     [BAK + "::test_an_install_keeps_save_db_in_my_games"], "installs moved to the instance folder"),
    ("save_engine.py", 'daiquiri.output.File(os.path.join(log_path(), "log.txt")',
     'daiquiri.output.File(os.path.join(log_path(), "log2.txt")',
     [BAK + "::test_a_crash_opens_the_log_the_server_writes"], "log written to another file than the one opened"),
    # B-O4 / B-D7: migration steps
    ("save_migration.py", 'if version == "0.04a" and version != target_version:',
     'if version == "0.04 a" and version != target_version:', [MIG + "::test_steps_that_only_change_the_version"],
     "0.04a step never runs"),
    ("save_migration.py", '        version = "0.07a"\r\n        session[\'save_version\'] = version',
     '        version = "0.07a"\r\n        session[\'save_version\'] = "0.06a"',
     [MIG + "::test_steps_that_only_change_the_version"], "0.07a version not written"),
    ("save_migration.py", '"Parliament": 3,', '"Parliament": 4,',
     [MIG + "::test_0_05a_staffs_the_built_government_buildings"], "Parliament crew 4"),
    ("save_migration.py", 'int(decoration.get("state")) >= 8', 'int(decoration.get("state")) > 8',
     [MIG + "::test_0_05a_staffs_the_built_government_buildings"], "state 8 not counted as built"),
    ("save_migration.py", 'decoration["crewInfo"] = [str(x) for x in old_crew]',
     'decoration["crewInfo"] = list(old_crew)',
     [MIG + "::test_0_07a_turns_the_0_08a_features_on_and_writes_crews_as_text"], "crews not written as text"),
    ("save_migration.py", 'if version and version.startswith("0.05a") and version != target_version:',
     'if version == "0.05a" and version != target_version:',
     [MIG + "::test_0_05a_staffs_the_built_government_buildings"], "patch releases of 0.05a not migrated"),
    ("save_migration.py", '        if not q["complete"]:\r\n', '        if True:\r\n',
     [MIG + "::test_0_02a_resets_the_open_quests_and_the_expansions"], "done quests reset too"),
    ("save_migration.py", '    extra["yield"] = 0', '    extra["yield"] = 1',
     [MIG + "::test_0_02a_resets_the_open_quests_and_the_expansions"], "0.02a step adds progress"),
    ("save_migration.py", "        unlock_expansion(206)\r\n", "",
     [MIG + "::test_0_02a_resets_the_open_quests_and_the_expansions"], "a starting expansion not unlocked"),
    ("save_migration.py", '["empire_tier_8"] = 4', '["empire_tier_8"] = 3',
     [MIG + "::test_0_07a_turns_the_0_08a_features_on_and_writes_crews_as_text"], "tier_8 not as a new save"),
    ("save_migration.py", '["empire_mech_fight_master"] = 3', '["empire_mech_fight_master"] = 4',
     [MIG + "::test_0_07a_turns_the_0_08a_features_on_and_writes_crews_as_text"], "titan fight variant off"),
    ("save_migration.py", '["empire_decorations_master"] = 2', '["empire_decorations_master"] = 3',
     [MIG + "::test_0_05a_turns_the_0_06a_features_on"], "decorations off"),
    ("save_migration.py", '["empires_support_units"] = 5', '["empires_support_units"] = 2',
     [MIG + "::test_0_05a_turns_the_0_06a_features_on"], "support units off"),
    # B-D5: dormant tree
    ("state_machine.py", '                      "has no click transition. Ignoring click.")\r\n                return',
     '                      "has no click transition. Ignoring click.")\r\n'
     '                do_state_rewards(state, cur_object.get(\'referenceItem\'), meta, playback_tend=playback_tend)\r\n'
     '                return',
     [EMP + "::test_click_on_dormant_tree_is_ignored"], "dormant click still gives the state's rewards"),
]


def run(wt, tests, timeout=200):
    env = dict(os.environ, PYTHONPATH=wt, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.Popen([PY, LAUNCHER, "-q", "-p", "no:cacheprovider", "-p", "no:warnings"] + tests, cwd=wt, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        p.communicate()
        return "timeout", []
    text = out.decode("utf-8", "replace")
    return ("passed" if p.returncode == 0 else "failed"), [l for l in text.splitlines() if l.startswith("FAILED")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    with open(a.out, "a", encoding="utf-8") as out:
        for fname, old, new, tests, what in MUTANTS:
            if a.only and a.only not in what:
                continue
            path = os.path.join(a.wt, fname)
            with open(path, encoding="utf-8", newline="") as f:
                original = f.read()
            assert original.count(old) == 1, (fname, old[:60], original.count(old))
            line = original[:original.index(old)].count("\n") + 1
            base, _ = run(a.wt, tests)
            assert base == "passed", ("tests fail without the mutant", tests)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(original.replace(old, new))
            try:
                result, failed = run(a.wt, tests)
            finally:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(original)
            for test in tests:
                hit = [l for l in failed if test.split("::")[1] in l]
                record = {"test": test, "mutant": what, "where": "%s:%d" % (fname, line), "before": "passed",
                          "after": "failed" if hit else result if result == "timeout" else "passed",
                          "detail": hit[0][:200] if hit else ""}
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                print(record["after"], test, "|", what, flush=True)


if __name__ == "__main__":
    main()
