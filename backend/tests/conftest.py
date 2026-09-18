"""Shared pytest configuration: one unique temp DB per test session.

The app engine binds to Aletheia_DATABASE_URL at import time, so the URL
must be set before any test imports app modules. pytest loads conftest.py
first, which guarantees ordering. A unique file per session guarantees no
state leaks between pytest runs (a resolved incident from a previous run
must never suppress bootstrap's idempotency check in the next one).
"""
from __future__ import annotations

import os
import tempfile
import uuid

_test_dir = os.path.dirname(os.path.abspath(__file__))
_db_name = f"_test_{uuid.uuid4().hex[:8]}.db"
os.environ["Aletheia_DATABASE_URL"] = f"sqlite:///{os.path.join(_test_dir, _db_name)}"

