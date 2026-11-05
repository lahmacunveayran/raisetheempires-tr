import os

import editor
import pytest

import init_settings
import save_engine

# A test that makes the server fail must never open the crash log in a text editor on the screen of whoever runs the
# tests. This is set for the whole run, not per test: a request thread a failed test left behind can still fail after
# that test's monkeypatches are undone.
os.environ["EDITOR"] = os.environ["VISUAL"] = "no-editor-in-tests"
_no_editor = lambda *args, **kwargs: None
editor.edit = _no_editor
init_settings.crash_log = False
save_engine.set_crash_log(False)


@pytest.fixture(autouse=True)
def backup_db(monkeypatch, tmp_path):
    """Keep save game backups made during tests out of the real backups.db."""
    monkeypatch.setattr(save_engine, "backup_db_path", lambda: str(tmp_path / "backups.db"))
    return save_engine


@pytest.fixture(autouse=True)
def no_text_editor():
    """Put the guard back after a test that replaced it (monkeypatch undoes that test's own change)."""
    yield
    editor.edit = _no_editor
    init_settings.crash_log = False
    save_engine.set_crash_log(False)
