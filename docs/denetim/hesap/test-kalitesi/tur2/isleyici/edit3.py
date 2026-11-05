import sys
p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
start = s.index("db = empires_server.db\n")
end = s.index("@pytest.fixture(autouse=True)\ndef quiet")
s = s[:start] + s[end:]
for old, new in [
    ("import time\nimport types\nimport xml", "import time\nimport xml"),
    ("import flask_session.sqlalchemy.sqlalchemy as flask_session_sqlalchemy\nimport libscrc", "import libscrc"),
    ("import pytest\nfrom sqlalchemy import Column, DateTime, Integer, LargeBinary, String\n", "import pytest\n"),
    ('read back from the database after the call.\n', 'read back from the database after the call. `server` is the app as configure_app sets it up\n(conftest.py).\n'),
]:
    assert s.count(old) == 1, old
    s = s.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(s)
