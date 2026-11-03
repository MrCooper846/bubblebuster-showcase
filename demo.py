from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import ANALYST, PERIOD, SUBJECT, engine, migrate
from evidence import approve, ingest, promote
from manifest import freeze
from packages.db.models import FinancialFact, ScenarioOutput
from packages.ingestion.local_object_store import LocalObjectStore
from scenarios import ScenarioService
from temporal import known_at
from transmission import RuleStop, revenue_share_step


def day(n):
    return datetime(2031, 1, n, tzinfo=UTC)


def statement(session, store, version):
    published, acquired, reviewed, promoted = {1: (2, 4, 5, 5), 2: (8, 11, 11, 12)}[version]
    content = (Path(__file__).parent / "fixtures" / f"statement-{version}.txt").read_bytes()
    doc_id = ingest(session, store, content, version, day(published), day(acquired))
    approve(session, store, doc_id, ANALYST, day(reviewed))
    return promote(session, store, doc_id, simulated_promotion_at=day(promoted))


def state(session, cutoff):
    return session.scalar(
        known_at(
            select(FinancialFact).where(FinancialFact.financial_period_id == PERIOD),
            FinancialFact,
            cutoff,
        )
    )


def scenario(session, cutoff, code="CAPEX_PERCENT"):
    run = ScenarioService(session).run(
        subject_id=SUBJECT,
        analyst_id=ANALYST,
        name="Budget sensitivity",
        information_cutoff_at=cutoff,
        shocks={code: Decimal(10)},
    )
    return session.scalars(select(ScenarioOutput).where(ScenarioOutput.scenario_id == run.id)).one()


def main():
    migrate()
    store = LocalObjectStore("/archive")
    with Session(engine) as session, session.begin():
        statement(session, store, 1)
        early = state(session, day(6))
        digest, payload = freeze(session, day(6))
        statement(session, store, 2)
        late = state(session, day(12))
        replay = state(session, day(6))
        assert replay.id == early.id and freeze(session, day(6))[0] == digest
        for label, fact in (("Jan 06", early), ("Jan 12", late), ("Jan 06 replay", replay)):
            print(f"{label}: {fact.value} {fact.unit_code} | fact {fact.id}")
        for cutoff in (day(6), day(12)):
            result = scenario(session, cutoff)
            print(
                f"{cutoff.date()} | {result.formula} | +10% | {result.baseline_value} -> {result.shocked_value} {result.unit_code} | input {result.source_id}"
            )
        try:
            with session.begin_nested():
                scenario(session, day(6), "REVENUE_PERCENT")
        except ValueError as error:
            print(f"Blocked scenario: {error}")
        try:
            revenue_share_step(Decimal(-10), "PERCENT", None, "PERCENT")
        except RuleStop as error:
            print(f"Separate synthetic supplier example (no exposure lookup): {error}")
        print(f"Frozen input {digest}: {payload}")


if __name__ == "__main__":
    main()
