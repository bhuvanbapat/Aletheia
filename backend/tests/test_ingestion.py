"""Unit tests: ingestion (parsing, malformed, dedup, normalization)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ingestion import ingest_events, normalize_event
from app.models import Base, TelemetryEvent


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, future=True)()
    # reset dedup cache between tests
    import app.ingestion as ing

    ing._seen_hashes = None
    yield session
    session.close()
    ing._seen_hashes = None


def test_normalize_valid_event(db):
    raw = {
        "timestamp": "2026-09-01T10:00:00Z",
        "service": "payments-service",
        "severity": "error",  # lowercase -> normalized
        "event_type": "database_timeout",
        "message": "timeout",
        "metadata": {"timeout_ms": 5000},
    }
    normalized = normalize_event(raw)
    assert normalized is not None
    assert normalized["severity"] == "ERROR"
    assert normalized["service"] == "payments-service"
    assert normalized["environment"] == "production"


def test_normalize_malformed_events():
    assert normalize_event({"service": "x"}) is None  # no timestamp
    assert normalize_event({"timestamp": "2026-09-01T10:00:00Z"}) is None  # no service
    assert normalize_event("not a dict") is None
    assert normalize_event({"timestamp": "garbage", "service": "x"}) is None


def test_normalize_epoch_timestamp():
    normalized = normalize_event({"timestamp": 1750000000, "service": "s", "event_type": "e"})
    assert normalized is not None
    assert normalized["timestamp"].year == 2025


def test_ingest_skips_malformed_and_counts(db):
    batch = [
        {"timestamp": "2026-09-01T10:00:00Z", "service": "a", "event_type": "x", "message": "ok"},
        {"service": "missing-ts"},  # malformed
        "garbage",  # malformed
    ]
    stats = ingest_events(db, batch)
    assert stats["received"] == 3
    assert stats["accepted"] == 1
    assert stats["malformed"] == 2
    assert len(stats["parse_errors"]) >= 1


def test_ingest_deduplicates(db):
    event = {"timestamp": "2026-09-01T10:00:00Z", "service": "a", "event_type": "x", "message": "m"}
    first = ingest_events(db, [event])
    second = ingest_events(db, [dict(event)])  # same content
    assert first["accepted"] == 1
    assert second["duplicates"] == 1
    count = db.query(TelemetryEvent).count()
    assert count == 1


def test_ingest_out_of_order_and_duplicate_metadata(db):
    events = [
        {"timestamp": "2026-09-01T10:05:00Z", "service": "a", "event_type": "x"},
        {"timestamp": "2026-09-01T09:55:00Z", "service": "a", "event_type": "y"},  # out of order - fine
    ]
    stats = ingest_events(db, events)
    assert stats["accepted"] == 2
    # non-dict metadata is preserved defensively
    event = {"timestamp": "2026-09-01T10:10:00Z", "service": "a", "event_type": "z",
             "metadata": "not-a-dict"}
    stats = ingest_events(db, [event])
    assert stats["accepted"] == 1
