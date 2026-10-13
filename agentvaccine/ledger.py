"""Commitment ledger with an atomic reserve-and-check operation.

The ledger is the state the policy is checked against. Two concurrent
acceptances cannot both spend the same remaining allowance because
`reserve` holds a lock across the check and the update.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


class LedgerError(Exception):
    pass


@dataclass
class Commitment:
    commitment_id: str
    recipient: str
    amount: int          # pence
    status: str          # "pending" | "completed" | "revoked"


@dataclass
class Ledger:
    budget_total: int
    commitments: dict[str, Commitment] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def spent_or_reserved(self) -> int:
        return sum(c.amount for c in self.commitments.values() if c.status != "revoked")

    @property
    def remaining(self) -> int:
        return self.budget_total - self.spent_or_reserved

    def reserve(self, commitment_id: str, recipient: str, amount: int) -> Commitment:
        """Atomically check the aggregate and record a pending commitment."""
        with self._lock:
            if commitment_id in self.commitments:
                raise LedgerError(f"duplicate commitment {commitment_id}")
            if amount > self.remaining:
                raise LedgerError(
                    f"aggregate exceeded: {self.spent_or_reserved + amount} > {self.budget_total}"
                )
            c = Commitment(commitment_id, recipient, amount, "pending")
            self.commitments[commitment_id] = c
            return c

    def complete(self, commitment_id: str) -> None:
        with self._lock:
            self.commitments[commitment_id].status = "completed"

    def revoke(self, commitment_id: str) -> None:
        with self._lock:
            c = self.commitments[commitment_id]
            if c.status == "completed":
                raise LedgerError("cannot revoke a completed commitment")
            c.status = "revoked"

    def snapshot(self) -> dict:
        return {
            "budget_total": self.budget_total,
            "spent_or_reserved": self.spent_or_reserved,
            "remaining": self.remaining,
            "commitments": {k: vars(v) for k, v in self.commitments.items()},
        }
