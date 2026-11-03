"""Single generic percentage rule, adapted from TransmissionRuleEngine.apply."""

from decimal import Decimal


class RuleStop(ValueError):
    pass


def revenue_share_step(shock, unit, exposure, exposure_unit):
    if exposure is None:
        raise RuleStop("UNKNOWN_EXPOSURE_VALUE")
    if unit != "PERCENT" or exposure_unit != "PERCENT":
        raise RuleStop("INCOMPATIBLE_UNITS")
    return shock * Decimal(exposure) / Decimal(100)
