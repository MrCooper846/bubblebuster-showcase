from datetime import datetime

from sqlalchemy import Select, and_, or_

from packages.db.models import FinancialFact


def known_at[T](
    statement: Select[tuple[T]],
    model: type[FinancialFact],
    cutoff: datetime,
) -> Select[tuple[T]]:
    """Restrict a statement to rows visible in the half-open knowledge interval."""
    return statement.where(
        and_(model.known_from <= cutoff, or_(model.known_to.is_(None), model.known_to > cutoff))
    )
