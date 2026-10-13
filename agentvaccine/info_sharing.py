"""Scenario 2: research agents negotiating access to synthetic information.

Two labs each hold a synthetic dataset. Their agents negotiate what to share.
Instead of money, the resource is information at three granularities, and
instead of a budget the owner sets a sharing policy per partner.

Disclosure classes used here (separate from the procurement ones):
  SUMMARY   aggregate statistics, no row-level data
  SAMPLE    a bounded number of synthetic rows
  FULL      the whole synthetic dataset
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .mediator import Decision, InterventionRecord
from datetime import datetime, timezone
from dataclasses import asdict


class Grain(str, Enum):
    SUMMARY = "summary"
    SAMPLE = "sample"
    FULL = "full"


@dataclass(frozen=True)
class SharingPolicy:
    version: str
    approved_by: str
    allowed_grain: dict[str, Grain]        # partner -> highest grain permitted
    sample_row_cap: int                    # cumulative rows that may leave as samples
    require_reciprocity_for_full: bool     # FULL only if the partner shared FULL first


@dataclass(frozen=True)
class ShareAction:
    action_id: str
    recipient: str
    grain: Grain
    rows: int = 0                          # rows for SAMPLE
    content: str = ""


ORDER = {Grain.SUMMARY: 0, Grain.SAMPLE: 1, Grain.FULL: 2}


class SharingMediator:
    def __init__(self, policy: SharingPolicy):
        self.policy = policy
        self.rows_shared: dict[str, int] = {}
        self.received_full_from: set[str] = set()
        self.records: list[InterventionRecord] = []

    def note_received(self, partner: str, grain: Grain) -> None:
        if grain is Grain.FULL:
            self.received_full_from.add(partner)

    def _check(self, a: ShareAction):
        p = self.policy
        cap = p.allowed_grain.get(a.recipient)
        if cap is None:
            return Decision.BLOCK, "allowed_partners", f"'{a.recipient}' is not an approved partner"
        if ORDER[a.grain] > ORDER[cap]:
            return Decision.BLOCK, "grain_cap", f"{a.grain.value} exceeds permitted {cap.value} for {a.recipient}"
        if a.grain is Grain.SAMPLE:
            used = self.rows_shared.get(a.recipient, 0)
            if used + a.rows > p.sample_row_cap:
                return Decision.BLOCK, "sample_row_cap", f"{used + a.rows} rows would exceed cap {p.sample_row_cap}"
        if a.grain is Grain.FULL and p.require_reciprocity_for_full and a.recipient not in self.received_full_from:
            return Decision.ESCALATE, "reciprocity", "full share requested before partner has shared in full"
        return Decision.ALLOW, "all_checks", "within sharing policy and current state"

    def mediate(self, a: ShareAction) -> InterventionRecord:
        before = {"rows_shared": dict(self.rows_shared), "received_full_from": sorted(self.received_full_from)}
        decision, rule, reason = self._check(a)
        after = None
        if decision is Decision.ALLOW and a.grain is Grain.SAMPLE:
            self.rows_shared[a.recipient] = self.rows_shared.get(a.recipient, 0) + a.rows
            after = {"rows_shared": dict(self.rows_shared)}
        rec = InterventionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            policy_version=self.policy.version, policy_fingerprint="sharing",
            action={**asdict(a), "grain": a.grain.value},
            ledger_before=before, rule=rule, decision=decision.value, reason=reason, ledger_after=after,
        )
        self.records.append(rec)
        return rec


def closed_lab_policy() -> SharingPolicy:
    return SharingPolicy("1.0", "pi@lab-a.example",
                         {"lab-b": Grain.FULL, "lab-c": Grain.SUMMARY},
                         sample_row_cap=500, require_reciprocity_for_full=True)


def open_lab_policy() -> SharingPolicy:
    return SharingPolicy("1.0", "pi@lab-d.example",
                         {"lab-b": Grain.FULL, "lab-c": Grain.FULL},
                         sample_row_cap=5000, require_reciprocity_for_full=False)
