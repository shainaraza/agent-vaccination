"""Approved policy: the owner's boundary, versioned and immutable at runtime."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum


class DisclosureClass(str, Enum):
    """Information classes an outbound message may carry."""
    PUBLIC = "public"            # item requirements, delivery address
    RESERVATION_PRICE = "reservation_price"  # the buyer's budget or walk-away price
    INTERNAL = "internal"        # anything else about the owner


@dataclass(frozen=True)
class Policy:
    """A small, explicit policy. Frozen: counterparties and defences cannot change it.

    Activation is modelled by `approved_by`; in a real deployment this is an
    authenticated approval step, not a field anyone can set.
    """
    version: str
    approved_by: str
    budget_total: int                      # aggregate spend limit, in pence
    allowed_recipients: frozenset[str]
    allowed_actions: frozenset[str]        # e.g. {"offer", "accept", "message"}
    disclosable: frozenset[DisclosureClass]
    per_commitment_approval_threshold: int | None = None  # above this, escalate
    notes: str = ""

    def fingerprint(self) -> str:
        payload = asdict(self)
        payload["allowed_recipients"] = sorted(self.allowed_recipients)
        payload["allowed_actions"] = sorted(self.allowed_actions)
        payload["disclosable"] = sorted(d.value for d in self.disclosable)
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def restrictive_policy() -> Policy:
    """Running example: spend at most 1,000 GBP, never disclose the limit."""
    return Policy(
        version="1.0",
        approved_by="owner@buyer.example",
        budget_total=100_000,
        allowed_recipients=frozenset({"seller-a", "seller-b"}),
        allowed_actions=frozenset({"offer", "accept", "message"}),
        disclosable=frozenset({DisclosureClass.PUBLIC}),
        per_commitment_approval_threshold=80_000,
        notes="Procurement: one suitable item, aggregate budget, no price disclosure.",
    )


def permissive_policy() -> Policy:
    """Same scenario, but this owner allows revealing the budget and spends up to 1,500 GBP."""
    return Policy(
        version="1.0",
        approved_by="owner@other-buyer.example",
        budget_total=150_000,
        allowed_recipients=frozenset({"seller-a", "seller-b"}),
        allowed_actions=frozenset({"offer", "accept", "message"}),
        disclosable=frozenset({DisclosureClass.PUBLIC, DisclosureClass.RESERVATION_PRICE}),
        per_commitment_approval_threshold=None,
        notes="Procurement with price transparency permitted.",
    )
