import importlib
import os
import tempfile


def _repo_files(root):
    """Every file of the repository folder with its size and time, to see what a test run wrote there."""
    files = {}
    for folder, subfolders, names in os.walk(root):
        # not git's own folders, nor other checkouts inside this one (worktrees under .claude/, a nested clone): what
        # happens in them is not this run's doing
        subfolders[:] = [s for s in subfolders if s not in (".git", "__pycache__", ".pytest_cache", ".claude")
                         and not os.path.exists(os.path.join(folder, s, ".git"))]
        for name in names:
            # git's worktree link, coverage's data, and the reports pytest itself writes when asked to (CI's
            # --junitxml=test-results.xml and --cov-report=xml)
            if name in (".git", ".coverage", "test-results.xml", "coverage.xml") or name.startswith(".coverage."):
                continue
            path = os.path.join(folder, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            files[os.path.relpath(path, root)] = (stat.st_size, stat.st_mtime_ns)
    return files


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_BEFORE = _repo_files(REPO)  # before the server's modules are imported: importing them already wrote files

# What the server writes next to itself when it runs from source (MyGamesPath=. in RaiseTheEmpires.ini) goes to a
# temporary folder in the tests: the log (save_engine opens log.txt when it is imported) and the mods cache.
TEST_FOLDER = tempfile.mkdtemp(prefix="rte-tests-")

import daiquiri.output

_log_file_path = daiquiri.output._get_log_file_path  # where daiquiri's File output writes

import init_settings

init_settings.caching = False  # mod_engine writes cache/ at import when caching; no mod is on in mods/mods.conf
daiquiri.output._get_log_file_path = lambda *args: os.path.join(TEST_FOLDER, os.path.basename(_log_file_path(*args)))
try:
    import save_engine
finally:
    daiquiri.output._get_log_file_path = _log_file_path
save_engine.log_path = lambda: TEST_FOLDER  # before empires-server imports it: the crash log is the log file above

import editor
import pytest

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


@pytest.fixture(scope="session", autouse=True)
def _server_setup(tmp_path_factory):
    """empires-server's app set up once for the whole run with configure_app, the setup the server itself runs before
    it serves, with save.db in a temporary folder. It runs before any test sends a request (Flask allows no setup
    after the first one) and is set up only once (Flask-SQLAlchemy can be registered on an app only once), so the
    tests can run in any order. Until a test asks for `server`, the app answers as it did before: with the session
    interface and WSGI app it had (cookie sessions, no host check middleware)."""
    empires_server = importlib.import_module("empires-server")
    app = empires_server.app
    plain = app.session_interface, app.wsgi_app
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + (tmp_path_factory.mktemp("saves") / "save.db").as_posix()
    empires_server.configure_app(app)
    configured = app.session_interface, app.wsgi_app
    app.session_interface, app.wsgi_app = plain
    yield app, plain, configured
    with app.app_context():
        empires_server.db.engine.dispose()  # let the temporary save.db go


@pytest.fixture
def server(_server_setup):
    """The server's app as configure_app set it up: save games in save.db (flask-session with SQLAlchemy and
    msgspec), the save lock, the host check around the Socket.IO middleware."""
    app, plain, configured = _server_setup
    app.session_interface, app.wsgi_app = configured
    yield app
    app.session_interface, app.wsgi_app = plain


def pytest_sessionfinish(session, exitstatus):
    """Tests must not write into the repository folder (only into temporary folders)."""
    after = _repo_files(REPO)
    changed = sorted(path for path in set(after) | set(_REPO_BEFORE) if after.get(path) != _REPO_BEFORE.get(path))
    if changed:
        print("\nThe tests changed files in the repository folder:", *changed, sep="\n  ")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
