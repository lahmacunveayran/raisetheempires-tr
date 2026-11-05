import sys
from pathlib import Path

import save_engine


def database_paths(monkeypatch, my_games, root):
    """Where save.db and backups.db end up for a MyGamesPath and a Flask root folder."""
    my_games.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setitem(save_engine.config['InstallFolders'], 'MyGamesPath', str(my_games))
    save_db_path = save_engine.save_database_path(str(root), str(root / "instance"))
    return Path(save_db_path), Path(save_engine.backup_database_path(save_db_path))


def test_backups_next_to_save_db_when_running_from_source(monkeypatch, tmp_path):
    (tmp_path / "save.db").write_bytes(b"save")

    save_db, backups = database_paths(monkeypatch, tmp_path, tmp_path)

    assert save_db == tmp_path / "instance" / "save.db"
    assert backups == tmp_path / "instance" / "backups.db"


def test_backups_next_to_save_db_when_installed(monkeypatch, tmp_path):
    save_db, backups = database_paths(monkeypatch, tmp_path / "My Games", tmp_path / "app")

    assert save_db == tmp_path / "My Games" / "save.db"
    assert backups == tmp_path / "My Games" / "backups.db"


def test_backups_next_to_save_db_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "temp" / "_MEI12345"), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "empires-server.exe"))
    root = save_engine.base_path()
    assert root == tmp_path / "app"

    assert database_paths(monkeypatch, tmp_path / "My Games", root) == \
        (tmp_path / "My Games" / "save.db", tmp_path / "My Games" / "backups.db")
    # a portable exe with MyGamesPath=. next to it behaves like running from source
    assert database_paths(monkeypatch, root, root) == \
        (root / "instance" / "save.db", root / "instance" / "backups.db")


def test_backups_db_in_my_games_path_is_moved_next_to_save_db(monkeypatch, tmp_path):
    (tmp_path / "save.db").write_bytes(b"save")
    (tmp_path / "backups.db").write_bytes(b"old backups")

    save_db, backups = database_paths(monkeypatch, tmp_path, tmp_path)

    assert backups.read_bytes() == b"old backups"
    assert not (tmp_path / "backups.db").exists()
    assert (tmp_path / "backup-save-db" / "backups.db").read_bytes() == b"old backups"


def test_backups_db_next_to_save_db_is_never_overwritten(monkeypatch, tmp_path):
    (tmp_path / "instance").mkdir()
    (tmp_path / "instance" / "backups.db").write_bytes(b"current backups")
    (tmp_path / "backups.db").write_bytes(b"old backups")

    save_db, backups = database_paths(monkeypatch, tmp_path, tmp_path)

    assert backups.read_bytes() == b"current backups"
    assert (tmp_path / "backups.db").read_bytes() == b"old backups"
