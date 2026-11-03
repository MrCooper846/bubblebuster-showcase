"""Single generic percentage rule, adapted from TransmissionRuleEngine.apply."""

from decimal import Decimal, InvalidOperation


class RuleStop(ValueError):
    pass


def revenue_share_step(shock, unit, exposure, exposure_unit):
    if exposure is None:
        raise RuleStop("UNKNOWN_EXPOSURE_VALUE")
    if unit != "PERCENT" or exposure_unit != "PERCENT":
        raise RuleStop("INCOMPATIBLE_UNITS")
    try:
        share = Decimal(str(exposure))
    except InvalidOperation as error:
        raise RuleStop("INVALID_REVENUE_SHARE") from error
    if not share.is_finite() or not 0 <= share <= 100:
        raise RuleStop("INVALID_REVENUE_SHARE")
    try:
        change = Decimal(str(shock))
    except InvalidOperation as error:
        raise RuleStop("INVALID_SHOCK") from error
    if not change.is_finite():
        raise RuleStop("INVALID_SHOCK")
    return change * share / Decimal(100)
