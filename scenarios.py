from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from packages.db.models import (
    Entity,
    EntityType,
    FinancialFact,
    FinancialMetric,
    FinancialPeriod,
    Scenario,
    ScenarioOutput,
    ScenarioShock,
)


class ScenarioService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        *,
        subject_id: UUID,
        analyst_id: UUID,
        name: str,
        information_cutoff_at,
        shocks: dict[str, Decimal],
    ) -> Scenario:
        self._require_analyst(analyst_id)
        if self.session.get(Entity, subject_id) is None:
            raise ValueError("subject entity not found")
        if not name.strip() or not shocks:
            raise ValueError("scenario name and at least one shock are required")
        allowed = {"CAPEX_PERCENT", "REVENUE_PERCENT"}
        if not set(shocks) <= allowed:
            raise ValueError("unknown scenario shock")
        scenario = Scenario(
            subject_entity_id=subject_id,
            analyst_entity_id=analyst_id,
            name=name.strip(),
            information_cutoff_at=information_cutoff_at,
        )
        self.session.add(scenario)
        self.session.flush()
        self.session.add_all(
            ScenarioShock(scenario_id=scenario.id, shock_type=code, value=value)
            for code, value in sorted(shocks.items())
        )
        outputs = self._outputs(subject_id, information_cutoff_at, shocks)
        self.session.add_all(
            ScenarioOutput(scenario_id=scenario.id, **output) for output in outputs
        )
        self.session.flush()
        return scenario

    def _outputs(self, subject_id, cutoff, shocks) -> list[dict]:
        outputs: list[dict] = []
        financials = self._financials(subject_id, cutoff)
        for shock_code, metric_code in (
            ("REVENUE_PERCENT", "REVENUE"),
            ("CAPEX_PERCENT", "CAPEX"),
        ):
            if shock_code not in shocks:
                continue
            fact = financials.get(metric_code)
            if fact is None:
                raise ValueError(f"{metric_code} baseline is unavailable at the cutoff")
            baseline = self._normalise(fact)
            shock = shocks[shock_code]
            outputs.append(
                {
                    "metric_code": metric_code,
                    "baseline_value": baseline,
                    "shocked_value": baseline * (Decimal(1) + shock / Decimal(100)),
                    "unit_code": "USD",
                    "formula": f"baseline * (1 + {shock_code} / 100)",
                    "source_kind": "FINANCIAL_FACT",
                    "source_id": fact.id,
                }
            )
        return outputs

    def _financials(self, subject_id, cutoff) -> dict[str, FinancialFact]:
        rows = self.session.execute(
            select(FinancialFact, FinancialMetric.code)
            .join(FinancialPeriod, FinancialPeriod.id == FinancialFact.financial_period_id)
            .join(FinancialMetric, FinancialMetric.id == FinancialFact.financial_metric_id)
            .where(
                FinancialPeriod.company_entity_id == subject_id,
                FinancialFact.known_from <= cutoff,
                or_(FinancialFact.known_to.is_(None), FinancialFact.known_to > cutoff),
            )
            .order_by(
                FinancialPeriod.period_end.desc(), FinancialFact.known_from.desc(), FinancialFact.id
            )
        ).all()
        result: dict[str, FinancialFact] = {}
        for fact, code in rows:
            result.setdefault(code, fact)
        return result

    @staticmethod
    def _normalise(fact: FinancialFact) -> Decimal:
        multipliers = {
            "USD": Decimal(1),
            "USD_THOUSAND": Decimal(1000),
            "USD_MILLION": Decimal(1_000_000),
            "USD_BILLION": Decimal(1_000_000_000),
        }
        if fact.unit_code not in multipliers:
            raise ValueError("financial baseline requires a supported USD unit")
        return fact.value * multipliers[fact.unit_code]

    def _require_analyst(self, analyst_id: UUID) -> None:
        if (
            self.session.scalar(
                select(Entity.id)
                .join(EntityType, EntityType.id == Entity.entity_type_id)
                .where(Entity.id == analyst_id, EntityType.code == "ANALYST")
            )
            is None
        ):
            raise ValueError("analyst not found")
