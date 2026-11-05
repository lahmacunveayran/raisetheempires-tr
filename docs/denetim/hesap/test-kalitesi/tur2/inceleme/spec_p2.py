LABEL = "point 2: backups.db in MyGamesPath (old backup_db_path), no move"
MUTATIONS = [("save_engine.py",
              """    path = os.path.join(os.path.dirname(save_db_path), "backups.db")
    old_path = os.path.join(my_games_path(), "backups.db")
    if os.path.exists(old_path) and not os.path.exists(path):""",
              """    path = os.path.join(my_games_path(), "backups.db")
    old_path = os.path.join(my_games_path(), "backups.db")
    if False:""")]
T = "test/backup_test.py::"
TESTS = [T + "test_backups_next_to_save_db_when_running_from_source",
         T + "test_backups_next_to_save_db_when_installed",
         T + "test_backups_next_to_save_db_when_frozen",
         T + "test_backups_db_in_my_games_path_is_moved_next_to_save_db",
         T + "test_backups_db_next_to_save_db_is_never_overwritten"]
