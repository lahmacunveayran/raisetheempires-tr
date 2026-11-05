LABEL = "point 1: model maps to a different table than the sqlite3 version wrote (schema compatibility guard)"
MUTATIONS = [("save_engine.py", '''    __tablename__ = "backups"''', '''    __tablename__ = "save_backups"''')]
T = "test/backup_test.py::"
TESTS = [T + "test_backups_db_written_with_the_sqlite3_module_still_works"]
