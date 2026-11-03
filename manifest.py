"""Evidence-only adaptation of the forecast snapshot's canonical input digest."""

import hashlib
import json
from datetime import UTC, date

from sqlalchemy import select, text

from database import SUBJECT, PERIOD
from packages.db.models import Document, FinancialFact
from temporal import known_at


HORIZON_END = date(2031, 12, 31)


def freeze(session, cutoff):
    if cutoff.utcoffset() is None:
        raise ValueError("cutoff needs a timezone")
    cutoff = cutoff.astimezone(UTC)
    if cutoff.date() > HORIZON_END:
        raise ValueError("forecast cutoff falls after the target horizon")
    rows = session.execute(
        known_at(
            select(FinancialFact.id, Document.sha256)
            .join(Document, Document.id == FinancialFact.source_document_id)
            .where(FinancialFact.financial_period_id == PERIOD),
            FinancialFact,
            cutoff,
        ).order_by(FinancialFact.id)
    )
    payload = {
        "subject_id": str(SUBJECT),
        "target": "next fiscal year's capex in USD",
        "horizon_end": HORIZON_END.isoformat(),
        "cutoff": cutoff.isoformat(),
        "methodology": "reviewed-capex-inputs/v1",
        "inputs": [{"fact_id": str(fid), "source_sha256": sha} for fid, sha in rows],
    }
    if not payload["inputs"]:
        raise ValueError("no admissible reviewed input")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    session.execute(
        text(
            "INSERT INTO frozen_input VALUES (:digest,CAST(:payload AS jsonb)) ON CONFLICT DO NOTHING"
        ),
        {"digest": digest, "payload": canonical},
    )
    return digest, payload
