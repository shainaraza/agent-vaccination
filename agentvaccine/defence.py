"""Admission of learned defences: screening before a transferred defence may act.

A defence record is untrusted. Admission checks its structure and its
policy assumptions against the receiving policy. An admitted defence can
only propose typed actions, which still pass the mediator like any other.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .policy import Policy, DisclosureClass


@dataclass(frozen=True)
class DefenceRecord:
    record_id: str
    source: str                          # where it was learned
    trigger: str                         # plain-language condition
    proposed_response: str               # "block" | "message" | ...
    assumes_disclosable: tuple[DisclosureClass, ...] = ()
    assumes_recipients: tuple[str, ...] = ()
    test_cases: tuple[str, ...] = ()


@dataclass
class AdmissionResult:
    record_id: str
    admitted: bool
    reason: str
    transformations: list[str] = field(default_factory=list)


def admit(record: DefenceRecord, policy: Policy) -> AdmissionResult:
    """Deterministic screening. Never grants authority the policy lacks."""
    if not record.test_cases:
        return AdmissionResult(record.record_id, False, "no supporting test cases")
    for d in record.assumes_disclosable:
        if d not in policy.disclosable:
            return AdmissionResult(
                record.record_id, False,
                f"defence assumes '{d.value}' may be disclosed; receiving policy prohibits it",
            )
    unknown = [r for r in record.assumes_recipients if r not in policy.allowed_recipients]
    transformations = []
    if unknown:
        transformations.append(f"dropped recipients not in policy: {unknown}")
    if record.proposed_response not in {"block", "message", "escalate"}:
        return AdmissionResult(record.record_id, False, f"unsupported response '{record.proposed_response}'")
    return AdmissionResult(record.record_id, True, "compatible with receiving policy", transformations)
