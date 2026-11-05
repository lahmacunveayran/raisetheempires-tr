import copy
import configparser
import threading
import zlib
import json
import os
import shutil
import sys
from datetime import datetime
from functools import reduce
from pathlib import Path

import daiquiri
import editor
from flask import session,current_app
import logging

from flask_session.sqlalchemy import SqlAlchemySessionInterface
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import want_bytes
from sqlalchemy import Boolean, Column, Float, Index, Integer, LargeBinary, String, Text, create_engine, delete, \
    false, insert, inspect, select, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.schema import CreateColumn

import init_settings as settings
try:
    import cPickle as pickle
except ImportError:
    import pickle


crash_log = True

db = SQLAlchemy()

def lookup_object(id):
    [game_object] = [e for e in session['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


def lookup_object_save(save, id):
    [game_object] = [e for e in save['user_object']["userInfo"]["world"]["objects"] if e['id'] == id]
    return game_object


def lookup_objects_by_item_name(id):
    return [e for e in session['user_object']["userInfo"]["world"]["objects"] if e['itemName'] == id]


def lookup_objects_save_by_position(save, x, y, r):
    return [e for e in save['user_object']["userInfo"]["world"]["objects"]
            if x <= int(e["position"].split(",")[0]) <= (x + r) and
            y <= int(e["position"].split(",")[1]) <= (y + r)]


# Backups used to be stored inside the save as a chain (session["backup"]["backup"]...), so every level up added a
# full copy of the save to it and the whole chain was rewritten on every request. They now live in a separate
# database. Backups made on purpose (save editor, cheats, quest routes, ...) are all kept, of the automatic ones (level
# ups) only the newest settings.max_backups per save (--max-backups, 0 keeps all).
BACKUP_KEYS = ['user_object', 'quests', 'battle', 'fleets', 'population', 'saved', 'saved_on', 'save_version',
               'original_save_version']


BackupBase = declarative_base()


class Backup(BackupBase):
    """A save game backup. Same table and columns as the backups.db files written before with the sqlite3 module."""
    __tablename__ = "backups"
    __table_args__ = (Index("backups_save_id", "save_id", "id"), {"sqlite_autoincrement": True})

    id = Column(Integer, primary_key=True)
    save_id = Column(String(255), nullable=False)
    saved_on = Column(Float)
    replaced_on = Column(Float)
    save_version = Column(String(64))
    message = Column(Text)
    automatic = Column(Boolean, nullable=False, default=False, server_default=false())  # level ups
    data = Column(LargeBinary, nullable=False)  # zlib-compressed pickle of the BACKUP_KEYS of the save


backup_db_uri = None  # SQLAlchemy database URL of the backups, set at startup by use_backup_database()
_backup_engine = None
_backup_engine_lock = threading.Lock()


def use_backup_database(uri):
    global backup_db_uri, _backup_engine
    with _backup_engine_lock:
        if _backup_engine is not None:
            _backup_engine.dispose()
        backup_db_uri, _backup_engine = uri, None


def backup_database_path(save_db_path):
    """backups.db is kept next to save.db, wherever save_database_path() put it (the instance folder when running
    from source). One made by an earlier version in MyGamesPath is moved there once."""
    path = os.path.join(os.path.dirname(save_db_path), "backups.db")
    old_path = os.path.join(my_games_path(), "backups.db")
    if os.path.exists(old_path) and not os.path.exists(path):
        print("INFORMATION: Moving backups.db next to save.db")
        backup_save_dir_path = os.path.join(my_games_path(), "backup-save-db")
        os.makedirs(backup_save_dir_path, exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        shutil.copy(old_path, backup_save_dir_path)
        shutil.move(old_path, path)
        print("Moved your backups.db to", path, "and a backup can be found at", backup_save_dir_path)
    elif os.path.exists(old_path) and not os.path.samefile(old_path, path):
        print("WARNING: You have a backups.db in both", my_games_path(), "and next to save.db, only", path, "will be used!")
    return path


def _backup_db():
    global _backup_engine
    with _backup_engine_lock:
        if _backup_engine is None:
            if backup_db_uri is None:
                raise RuntimeError("No backup database, call use_backup_database() first")
            _backup_engine = create_engine(backup_db_uri)
            BackupBase.metadata.create_all(_backup_engine)
            if "automatic" not in [c["name"] for c in inspect(_backup_engine).get_columns("backups")]:
                # backups.db from before automatic backups were told apart, its backups count as made on purpose
                column = CreateColumn(Backup.__table__.c.automatic).compile(dialect=_backup_engine.dialect)
                with _backup_engine.begin() as con:
                    con.execute(text(f"ALTER TABLE backups ADD COLUMN {column}"))
        return _backup_engine


def _save_id(save):
    """The server side session id, also for saves read from the database (where it is "session:<sid>")."""
    sid = str(getattr(save, "sid", None) or save.get("session_id") or "local")
    return sid[len("session:"):] if sid.startswith("session:") else sid


def store_backup(save_id, backup, automatic=False):
    with _backup_db().begin() as con:
        con.execute(insert(Backup).values(
            save_id=save_id, saved_on=backup.get('saved_on'), replaced_on=backup.get('replaced_on'),
            save_version=str(backup.get('save_version')), message=str(backup.get('message', '')),
            automatic=automatic, data=zlib.compress(pickle.dumps(backup, pickle.HIGHEST_PROTOCOL))))
        if automatic and settings.max_backups:
            old_ids = con.scalars(select(Backup.id).where(Backup.save_id == save_id, Backup.automatic)
                                  .order_by(Backup.id.desc()).offset(settings.max_backups)).all()
            if old_ids:
                con.execute(delete(Backup).where(Backup.id.in_(old_ids)))


def list_backups(save):
    """Newest first: [(id, {'saved_on', 'replaced_on', 'save_version', 'message'})]."""
    with _backup_db().connect() as con:
        rows = con.execute(select(Backup.id, Backup.saved_on, Backup.replaced_on, Backup.save_version, Backup.message)
                           .where(Backup.save_id == _save_id(save)).order_by(Backup.id.desc())).all()
    return [(r.id, {'saved_on': r.saved_on, 'replaced_on': r.replaced_on, 'save_version': r.save_version,
                    'message': r.message}) for r in rows]


def load_backup(save, backup_id):
    with _backup_db().connect() as con:
        data = con.scalar(select(Backup.data).where(Backup.save_id == _save_id(save), Backup.id == backup_id))
    return pickle.loads(zlib.decompress(data)) if data is not None else None


def move_nested_backups(save):
    """Moves an old in-save backup chain to the backup database. Returns True if the save was changed."""
    chain = []
    node = save
    while isinstance(node.get("backup"), dict):
        node = node["backup"]
        chain.append({k: v for k, v in node.items() if k != "backup"})
    if "backup" not in save:
        return False
    for backup in reversed(chain):  # oldest first, so ids keep the original order
        store_backup(_save_id(save), backup, str(backup.get("message", "")).startswith("Level "))
    del save["backup"]
    return True


def create_backup(message, automatic=False):
    """automatic: made without the player asking for it (level ups), only the newest settings.max_backups are kept."""
    timestamp = datetime.now().timestamp()
    backup = copy.deepcopy({k: v for k, v in session.items() if k in BACKUP_KEYS})
    backup['replaced_on'] = timestamp
    backup['message'] = message
    store_backup(_save_id(session), backup, automatic)
    session['saved_on'] = timestamp

def save_database_path(root_path, instance_path):
    save_db_path = os.path.join(my_games_path(), "save.db")

    if os.path.samefile(my_games_path(), root_path):
        new_save_db_path = os.path.join(instance_path, "save.db")
        if os.path.exists(save_db_path):
            if not os.path.exists(new_save_db_path):
                print("INFORMATION: You're running from source, and because of Flask update save.db has to be moved to the instance folder. Installs out of folder should be unaffected")
                if not os.path.exists(instance_path):
                    os.makedirs(instance_path)
                backup_save_dir_path = os.path.join(my_games_path(), "backup-save-db")
                if not os.path.exists(backup_save_dir_path):
                    os.makedirs(backup_save_dir_path)
                shutil.copy(save_db_path, backup_save_dir_path)
                shutil.move(save_db_path, new_save_db_path)
                print("Moved your save.db to", instance_path, "and a backup can be found at", backup_save_dir_path)
            else:
                print("WARNING: You have a save.db in both the root as the instance folder (when running from source), only the instance one will be used!")
        save_db_path = new_save_db_path

    print("SQLITE", f"sqlite:///{save_db_path}")

    return save_db_path


def my_games_path():
    return config['InstallFolders']['MyGamesPath']


def install_path():
    return config['InstallFolders']['InstallPath']


def base_path():
    return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent


def log_path():
    if os.path.exists(my_games_path()):
        return my_games_path()
    else:
        print("Warning: folder in My games missing, falling back to install folder.")
        return "."


def set_crash_log(toggle):
    global crash_log

    crash_log = toggle


def exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    if crash_log:
        text = editor.edit(filename=os.path.join(log_path(), "log.txt"))

# logger = logging.getLogger(__name__)
# handler = logging.StreamHandler(stream=sys.stdout)
# logger.addHandler(handler)


config = configparser.ConfigParser()
config.read('RaiseTheEmpires.ini')

daiquiri.setup(level=logging.INFO, outputs=(
    daiquiri.output.Stream(sys.stdout),
    daiquiri.output.File(os.path.join(log_path(), "log.txt"), formatter=daiquiri.formatter.TEXT_FORMATTER),
    ))
logger = daiquiri.getLogger(__name__)

sys.excepthook = exception_handler


def get_all_sessions():
    sess_int: SqlAlchemySessionInterface = current_app.session_interface
    sess_model = sess_int.sql_session_model
    # record = sess_model.query.filter_by(
    #         id=17).first()
    records = sess_model.query.all()
    return records

def decode_save(serialized_save):
    try:
        sess_int: SqlAlchemySessionInterface = current_app.session_interface
        return sess_int.serializer.decode(serialized_save)
    except Exception as e:
        print("Skipping corrupt save")
        print(e)
        return None


def get_saves():
    return [enrich_save(save, record) for record in get_all_sessions() for save in [decode_save(want_bytes(record.data))] if save is not None and 'user_object' in save]


def enrich_save(save, record):
    save["session_id"] = record.session_id
    return save


def store_session(save):
    sess_int: SqlAlchemySessionInterface = current_app.session_interface
    sess_model = sess_int.sql_session_model
    record = sess_model.query.filter_by(
            session_id=save["session_id"]).first()

    record.data = pickle.dumps(dict(save))
    sess_int.db.session.commit()


def validate_save(save, blank_allowed = False):
    player = get_dict(save, "user_object", "userInfo", "player")
    return (isinstance(player.get("level"), int) and
            isinstance(player.get("uid", {}), int) and
            isinstance(get_dict(save, "user_object", "userInfo").get("worldName"), str) and
            isinstance(player.get("xp", {}), (int, float)) and
            isinstance(player.get("playerResourceType", {}), int) and
            isinstance(get_dict(save, "user_object", "userInfo", "world", "resources").get("coins"), (int, float)) and
            isinstance(player.get("socialXpGood", {}), (int, float)) and
            isinstance(player.get("socialLevelGood", {}), int) and
            isinstance(player.get("socialXpBad", {}), (int, float)) and
            isinstance(player.get("socialLevelBad", {}), int)) or \
           (blank_allowed and 'user_object' not in save)


def get_dict(*args):
    return reduce((lambda a, b: a.get(b, {}) if isinstance(a.get(b, {}), dict) else {}), args)


class InvalidSaveException(Exception):
    """Exception when save is invalid while loading."""
    pass

