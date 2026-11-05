import os, runpy
here = os.path.dirname(os.path.abspath(__file__))
T = "test/backup_test.py::"
CASES = [
    ("point 3: pruning ignores the automatic flag (prunes manual backups too)",
     [("save_engine.py", "Backup.save_id == save_id, Backup.automatic)", "Backup.save_id == save_id)")],
     [T + "test_level_ups_do_not_push_out_backups_made_on_purpose"]),
    ("point 3: level ups in quest_engine not marked automatic",
     [("quest_engine.py", 'create_backup("Level " + level["-num"], automatic=True)', 'create_backup("Level " + level["-num"])')],
     [T + "test_level_ups_do_not_push_out_backups_made_on_purpose"]),
    ("point 3: --max-backups not accepted by getopt",
     [("init_settings.py", ', "max-backups="]', ']')],
     [T + "test_max_backups_option_limits_automatic_backups"]),
    ("point 3: --max-backups=0 not treated as unlimited",
     [("save_engine.py", "if automatic and settings.max_backups:", "if automatic:")],
     [T + "test_max_backups_option_limits_automatic_backups"]),
    ("point 3: no automatic column migration for backups.db from the sqlite3 version",
     [("save_engine.py", 'if "automatic" not in [', 'if False and "automatic" not in [')],
     [T + "test_backups_db_written_with_the_sqlite3_module_still_works"]),
]
