"""The mediator: every proposed action passes here before it has an effect.

Deterministic checks only. A learned risk estimate could be added as a
further step that may tighten (escalate) but never override a failed check.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum

from .ledger import Ledger, LedgerError
from .policy import Policy, DisclosureClass


class Decision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class Action:
    """A typed proposal from the agent. Only typed actions are mediated."""
    action_id: str
    kind: str                      # "offer" | "accept" | "message"
    recipient: str
    amount: int | None = None      # pence, for offer/accept
    disclosure: tuple[DisclosureClass, ...] = ()   # classes the content carries
    content: str = ""
    source: str = "agent"          # "agent" or "defence:<record id>"


@dataclass
class InterventionRecord:
    """Evidence a reviewer can replay the decision from."""
    timestamp: str
    policy_version: str
    policy_fingerprint: str
    action: dict
    ledger_before: dict
    rule: str
    decision: str
    reason: str
    ledger_after: dict | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


class Mediator:
    def __init__(self, policy: Policy):
        self.policy = policy
        self.ledger = Ledger(policy.budget_total)
        self.records: list[InterventionRecord] = []

    # --- checks, in order; the first failure decides -------------------------

    def _check(self, a: Action) -> tuple[Decision, str, str]:
        p = self.policy
        if a.kind not in p.allowed_actions:
            return Decision.BLOCK, "allowed_actions", f"action kind '{a.kind}' not permitted"
        if a.recipient not in p.allowed_recipients:
            return Decision.BLOCK, "allowed_recipients", f"recipient '{a.recipient}' not permitted"
        for d in a.disclosure:
            if d not in p.disclosable:
                return Decision.BLOCK, "disclosure_class", f"content carries '{d.value}', which this policy prohibits"
        if a.kind == "accept":
            if a.amount is None:
                return Decision.BLOCK, "typed_action", "acceptance without an amount"
            if p.per_commitment_approval_threshold is not None and a.amount > p.per_commitment_approval_threshold:
                return Decision.ESCALATE, "approval_threshold", f"{a.amount} exceeds per-commitment threshold {p.per_commitment_approval_threshold}"
            if a.amount > self.ledger.remaining:
                return Decision.BLOCK, "aggregate_budget", f"{self.ledger.spent_or_reserved + a.amount} would exceed total {p.budget_total}"
        return Decision.ALLOW, "all_checks", "within policy and current state"

    # --- the single entry point --------------------------------------------

    def mediate(self, a: Action) -> InterventionRecord:
        before = self.ledger.snapshot()
        decision, rule, reason = self._check(a)
        after = None
        if decision is Decision.ALLOW and a.kind == "accept":
            try:
                # The ledger re-checks atomically; a race between two accepts
                # is caught here even if both passed _check.
                self.ledger.reserve(a.action_id, a.recipient, a.amount)
                after = self.ledger.snapshot()
            except LedgerError as e:
                decision, rule, reason = Decision.BLOCK, "aggregate_budget_atomic", str(e)
        rec = InterventionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            policy_version=self.policy.version,
            policy_fingerprint=self.policy.fingerprint(),
            action=asdict(a),
            ledger_before=before,
            rule=rule,
            decision=decision.value,
            reason=reason,
            ledger_after=after,
        )
        self.records.append(rec)
        return rec
