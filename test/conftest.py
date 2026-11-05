import pytest

import save_engine


@pytest.fixture(autouse=True)
def backup_db(tmp_path):
    """Keep save game backups made during tests out of the real backups.db."""
    previous = save_engine.backup_db_uri
    save_engine.use_backup_database(f"sqlite:///{tmp_path / 'backups.db'}")
    yield save_engine
    save_engine.use_backup_database(previous)
