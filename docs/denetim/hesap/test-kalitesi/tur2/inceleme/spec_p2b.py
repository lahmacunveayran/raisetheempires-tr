LABEL = "point 2: path next to save.db but the move overwrites an existing target"
MUTATIONS = [("save_engine.py",
              """    if os.path.exists(old_path) and not os.path.exists(path):""",
              """    if os.path.exists(old_path) and not os.path.samefile(os.path.dirname(old_path), os.path.dirname(path)):""")]
T = "test/backup_test.py::"
TESTS = [T + "test_backups_db_in_my_games_path_is_moved_next_to_save_db",
         T + "test_backups_db_next_to_save_db_is_never_overwritten"]
