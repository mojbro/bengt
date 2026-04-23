"""Daily spend cap (PRD §6.7).

Reads from AuditService's aggregate cost. UTC day boundary — simple and
unambiguous; frontend displays remaining budget in local time if we ever
want that granularity.
"""

from dataclasses import dataclass

from app.db import AuditService


@dataclass
class BudgetStatus:
    cap_usd: float
    spent_usd: float
    remaining_usd: float
    exceeded: bool


class BudgetService:
    def __init__(self, audit: AuditService, cap_usd: float):
        self.audit = audit
        self.cap_usd = float(cap_usd)

    def status(self) -> BudgetStatus:
        spent = self.audit.cost_today_utc()
        remaining = max(0.0, self.cap_usd - spent)
        return BudgetStatus(
            cap_usd=self.cap_usd,
            spent_usd=spent,
            remaining_usd=remaining,
            exceeded=spent >= self.cap_usd,
        )

    def exceeded(self) -> bool:
        return self.status().exceeded
