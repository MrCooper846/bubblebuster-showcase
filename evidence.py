"""Bounded review/promotion adapter for the synthetic financial statements."""

import re
from decimal import Decimal

from sqlalchemy import select, text

from database import PERIOD, SUBJECT, key
from packages.db.models import Document, Entity, EntityType, FinancialFact
from packages.ingestion.object_store import StoredObjectRef, content_addressed_key


def lock_subject(session):
    session.scalar(select(Entity.id).where(Entity.id == SUBJECT).with_for_update())


def extract(content):
    lines = content.decode().splitlines()
    if lines[:1] != ["Reedglass Compute | Lantern Yard data centre | year ended 2030-12-31"]:
        raise ValueError("unresolved issuer or period")
    matches = [(line, re.fullmatch(r"(\w+) = (\d+(?:\.\d+)?) (\w+)", line)) for line in lines]
    fragments = [(line, match.groups()) for line, match in matches if match]
    if len(fragments) != 1:
        raise ValueError("expected one cited numeric statement")
    line, (metric, amount, unit) = fragments[0]
    return {"fragment": line, "metric": metric, "amount": Decimal(amount), "unit": unit}


def ingest(session, store, content, version, published, acquired):
    fields = extract(content)
    obj = store.put(content, content_type="text/plain")
    lock_subject(session)
    doc_id = key(obj.sha256)
    existing = session.get(Document, doc_id)
    if existing:
        if (existing.version, existing.published_at, existing.acquired_at) != (
            version,
            published,
            acquired,
        ):
            raise ValueError("document retry has conflicting metadata")
        return doc_id
    session.add(
        Document(
            id=doc_id,
            subject_id=SUBJECT,
            version=version,
            sha256=obj.sha256,
            published_at=published,
            acquired_at=acquired,
        )
    )
    session.flush()
    session.execute(
        text("INSERT INTO proposal VALUES (:id,:fragment,:metric,:amount,:unit)"),
        {"id": doc_id, **fields},
    )
    return doc_id


def validate(session, store, doc_id):
    doc = session.get(Document, doc_id)
    proposal = (
        session.execute(
            text("SELECT fragment,metric,amount,unit FROM proposal WHERE document_id=:id"),
            {"id": doc_id},
        )
        .mappings()
        .one()
    )
    ref = StoredObjectRef(
        store.provider, store.bucket_name, content_addressed_key(doc.sha256), doc.sha256
    )
    if extract(store.get(ref)) != dict(proposal):
        raise ValueError("proposal disagrees with cited artifact")
    if proposal["metric"] != "CAPEX" or proposal["unit"] not in {"USD", "USD_MILLION"}:
        raise ValueError("unregistered metric or incompatible unit")
    return proposal


def approve(session, store, doc_id, reviewer, when):
    lock_subject(session)
    role = session.scalar(select(EntityType.code).join(Entity).where(Entity.id == reviewer))
    if role != "ANALYST":
        raise ValueError("reviewer must be a canonical ANALYST entity")
    validate(session, store, doc_id)
    if when < session.get(Document, doc_id).acquired_at:
        raise ValueError("review precedes acquisition")
    session.execute(
        text("INSERT INTO approval VALUES (:id,:who,:at) ON CONFLICT DO NOTHING"),
        {"id": doc_id, "who": reviewer, "at": when},
    )


def promote(session, store, doc_id):
    lock_subject(session)
    previous = session.scalar(
        select(FinancialFact).where(FinancialFact.source_document_id == doc_id)
    )
    if previous:
        return previous
    when = session.scalar(
        text("SELECT reviewed_at FROM approval WHERE document_id=:id"), {"id": doc_id}
    )
    if when is None:
        raise ValueError("proposal must be approved before promotion")
    proposal = validate(session, store, doc_id)
    current = session.scalar(
        select(FinancialFact).where(
            FinancialFact.financial_period_id == PERIOD,
            FinancialFact.financial_metric_id == 1,
            FinancialFact.known_to.is_(None),
        )
    )
    if current:
        if when <= current.known_from:
            raise ValueError("supersession requires a later review")
        current.known_to = when
        session.flush()
    fact = FinancialFact(
        id=key(str(doc_id) + "/capex"),
        financial_period_id=PERIOD,
        financial_metric_id=1,
        value=proposal["amount"],
        unit_code=proposal["unit"],
        taxonomy_concept="CAPEX",
        accession_number=str(doc_id),
        source_document_id=doc_id,
        known_from=when,
    )
    session.add(fact)
    session.flush()
    return fact
