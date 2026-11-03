from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from database import ANALYST, SUBJECT, engine, initialize
from demo import day, scenario, state, statement
from evidence import approve, ingest, promote
from manifest import freeze
from packages.db.models import FinancialFact
from packages.ingestion.local_object_store import LocalObjectStore
from packages.ingestion.object_store import ObjectIntegrityError
from scenarios import ScenarioService
from transmission import RuleStop, revenue_share_step


@pytest.fixture
def db():
    # The schema and its data disappear with the enclosing transaction.
    with engine.connect() as cx:
        outer = cx.begin()
        cx.exec_driver_sql("CREATE SCHEMA case_test")
        cx.exec_driver_sql("SET LOCAL search_path = case_test, public")
        initialize(cx)
        with Session(cx) as session:
            yield session
        outer.rollback()


@pytest.fixture
def store(tmp_path):
    return LocalObjectStore(tmp_path)


def test_replay_and_manifest_survive_correction(db, store):
    first = statement(db, store, 1)
    frozen = freeze(db, day(6))
    second = statement(db, store, 2)
    assert state(db, day(4)) is None
    assert state(db, day(11)).id == first.id
    assert state(db, day(12)).id == second.id
    assert first.known_to == second.known_from
    assert state(db, day(6)).value == 12
    assert freeze(db, day(6)) == frozen
    assert frozen[1]["inputs"][0]["fact_id"] == str(first.id)
    assert freeze(db, day(12))[0] != frozen[0]
    with pytest.raises(ValueError, match="no admissible"):
        freeze(db, day(3))


def test_review_without_promotion_preserves_earlier_state(db, store):
    first = statement(db, store, 1)
    data = Path("fixtures/statement-2.txt").read_bytes()
    doc = ingest(db, store, data, 2, day(8), day(10))
    approve(db, store, doc, ANALYST, day(10))
    frozen = freeze(db, day(11))
    assert state(db, day(11)).id == first.id
    with pytest.raises(ValueError, match="after approval"):
        promote(db, store, doc, simulated_promotion_at=day(9))
    second = promote(db, store, doc, simulated_promotion_at=day(12))
    assert first.known_to == second.known_from == day(12)
    assert state(db, day(11)).id == first.id
    assert freeze(db, day(11)) == frozen
    assert state(db, day(12)).id == second.id
    assert promote(db, store, doc, simulated_promotion_at=day(13)).known_from == day(12)


def test_default_promotion_uses_database_time(db, store):
    before = db.scalar(text("SELECT clock_timestamp()"))
    review = before - timedelta(days=1)
    data = Path("fixtures/statement-1.txt").read_bytes()
    doc = ingest(db, store, data, 1, review, review)
    approve(db, store, doc, ANALYST, review)
    fact = promote(db, store, doc)
    assert before <= fact.known_from <= db.scalar(text("SELECT clock_timestamp()"))
    assert state(db, review) is None


def test_forecast_horizon_uses_utc(db, store):
    statement(db, store, 1)
    # The two supplied offsets fall on opposite local dates around UTC year-end.
    last = datetime.fromisoformat("2032-01-01T00:59:59.999999+01:00")
    first_closed = datetime.fromisoformat("2031-12-31T23:00:00-01:00")
    assert freeze(db, last) == freeze(db, last.astimezone(UTC))
    for cutoff in (first_closed, first_closed + timedelta(days=1)):
        with pytest.raises(ValueError, match="after the target horizon"):
            freeze(db, cutoff)
    assert db.scalar(text("SELECT count(*) FROM frozen_input")) == 1


def test_idempotent_processing(db, store):
    assert statement(db, store, 1).id == statement(db, store, 1).id
    assert db.scalar(select(func.count()).select_from(FinancialFact)) == 1
    for table in ("document", "proposal", "approval"):
        assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 1


def test_review_boundary(db, store):
    data = Path("fixtures/statement-1.txt").read_bytes()
    doc = ingest(db, store, data, 1, day(2), day(4))
    with pytest.raises(ValueError, match="approved"):
        promote(db, store, doc)
    with pytest.raises(ValueError, match="ANALYST"):
        approve(db, store, doc, SUBJECT, day(5))
    with pytest.raises(ValueError, match="precedes acquisition"):
        approve(db, store, doc, ANALYST, day(3))
    with pytest.raises(ValueError, match="conflicting metadata"):
        ingest(db, store, data, 1, day(2), day(6))
    obj = store.put(data)
    store.path_for(obj.ref).write_bytes(b"altered")
    with pytest.raises(ObjectIntegrityError):
        approve(db, store, doc, ANALYST, day(5))


def test_invalid_extracted_unit(db, store):
    data = Path("fixtures/statement-1.txt").read_bytes().replace(b"USD_MILLION", b"MW")
    doc = ingest(db, store, data, 1, day(2), day(4))
    with pytest.raises(ValueError, match="incompatible unit"):
        approve(db, store, doc, ANALYST, day(5))


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE financial_fact SET value=0",
        "DELETE FROM financial_fact",
        "UPDATE financial_fact SET known_to=NULL WHERE known_to IS NOT NULL",
        "DELETE FROM frozen_input",
        "UPDATE proposal SET fragment='other'",
        "UPDATE document SET published_at=acquired_at",
        "DELETE FROM approval",
    ],
)
def test_database_rejects_rewrites(db, store, sql):
    statement(db, store, 1)
    freeze(db, day(6))
    statement(db, store, 2)
    with pytest.raises(DBAPIError, match="superseded|immutable"), db.begin_nested():
        db.execute(text(sql))


def test_cutoff_specific_scenario(db, store):
    statement(db, store, 1)
    statement(db, store, 2)
    a, b = scenario(db, day(6)), scenario(db, day(6))
    assert (a.shocked_value, a.source_id, a.formula) == (b.shocked_value, b.source_id, b.formula)
    assert a.shocked_value == Decimal("13200000")
    assert scenario(db, day(12)).shocked_value == Decimal("16500000")
    with pytest.raises(ValueError, match="baseline is unavailable"), db.begin_nested():
        scenario(db, day(4))
    with pytest.raises(ValueError, match="baseline is unavailable"), db.begin_nested():
        scenario(db, day(6), "REVENUE_PERCENT")
    with pytest.raises(ValueError, match="USD unit"):
        ScenarioService._normalise(SimpleNamespace(value=Decimal(12), unit_code="MW"))


def test_transmission_refusals():
    with pytest.raises(RuleStop, match="UNKNOWN_EXPOSURE_VALUE"):
        revenue_share_step(-10, "PERCENT", None, "PERCENT")
    with pytest.raises(RuleStop, match="INCOMPATIBLE_UNITS"):
        revenue_share_step(-10, "USD", 20, "PERCENT")
    assert revenue_share_step(-10, "PERCENT", 20, "PERCENT") == -2
    assert revenue_share_step(-10, "PERCENT", 0, "PERCENT") == 0
    assert revenue_share_step(-10, "PERCENT", 100, "PERCENT") == -10


@pytest.mark.parametrize(
    "share", ["-0.01", "100.01", "NaN", "sNaN", "Infinity", "-Infinity", "bad"]
)
def test_invalid_revenue_share(share):
    with pytest.raises(RuleStop, match="INVALID_REVENUE_SHARE"):
        revenue_share_step(-10, "PERCENT", share, "PERCENT")


@pytest.mark.parametrize("shock", ["NaN", "Infinity", "-Infinity", "bad"])
def test_invalid_shock(shock):
    with pytest.raises(RuleStop, match="INVALID_SHOCK"):
        revenue_share_step(shock, "PERCENT", 20, "PERCENT")
