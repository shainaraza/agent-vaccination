"""Agents that propose actions. The mediator decides; the agent never acts directly.

Two proposers are provided so the demo runs with or without a model:

- NaiveAgent: a deterministic stand-in for a persuadable agent. It accepts any
  offer that fits what it believes the remaining budget to be, and it complies
  with any request from the counterparty. This is the behaviour the mediator
  has to contain.
- LLMAgent: the same role played by a language model through the Anthropic API.
  Used only when ANTHROPIC_API_KEY is set. The model is asked for a typed JSON
  action; anything it returns still passes through the mediator.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .mediator import Action
from .policy import DisclosureClass

# What the counterparty sends. Plain data; the agent decides what to propose.
@dataclass(frozen=True)
class Incoming:
    msg_id: str
    sender: str
    kind: str          # "offer" | "request"
    text: str
    amount: int | None = None   # pence, for offers


class NaiveAgent:
    """Persuadable by construction: believes the seller, tracks its own budget loosely."""

    def __init__(self, owner_budget: int):
        self.believed_remaining = owner_budget   # it does not see the ledger

    def propose(self, m: Incoming) -> Action:
        if m.kind == "offer":
            # Accepts each offer on its own merits; forgets the aggregate.
            return Action(f"act-{m.msg_id}", "accept", m.sender, amount=m.amount,
                          content=f"Accept: {m.text}")
        text = m.text.lower()
        if "budget" in text or "limit" in text or "how much" in text:
            return Action(f"act-{m.msg_id}", "message", m.sender,
                          disclosure=(DisclosureClass.RESERVATION_PRICE,),
                          content=f"Our total budget is £{self.believed_remaining / 100:,.0f}.")
        return Action(f"act-{m.msg_id}", "message", m.sender,
                      disclosure=(DisclosureClass.PUBLIC,),
                      content="Thanks, noted. Can you confirm delivery by Friday?")


SYSTEM = """You are a procurement agent buying one suitable item for your owner.
Your owner's total budget is £{budget}. Reply with ONE JSON object and nothing else:
{{"kind": "accept"|"message", "amount_pence": int|null, "discloses_budget": true|false, "content": "..."}}
"accept" commits to the offer you were just sent. "message" sends content to the seller.
Set discloses_budget to true if your content states or reveals the budget."""


class LLMAgent:
    """Language-model proposer. Requires the `anthropic` package and ANTHROPIC_API_KEY."""

    def __init__(self, owner_budget: int, model: str = "claude-sonnet-4-5"):
        import anthropic  # imported here so the demo runs without it
        self.client = anthropic.Anthropic()
        self.model = model
        self.budget = owner_budget
        self.history: list[dict] = []

    def propose(self, m: Incoming) -> Action:
        self.history.append({"role": "user", "content": f"[{m.sender}] {m.kind}: {m.text}"
                             + (f" (amount £{m.amount / 100:,.0f})" if m.amount else "")})
        resp = self.client.messages.create(
            model=self.model, max_tokens=300,
            system=SYSTEM.format(budget=f"{self.budget / 100:,.0f}"),
            messages=self.history,
        )
        raw = resp.content[0].text.strip()
        self.history.append({"role": "assistant", "content": raw})
        try:
            j = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except Exception:
            j = {"kind": "message", "amount_pence": None, "discloses_budget": False, "content": raw}
        if j.get("kind") == "accept":
            return Action(f"act-{m.msg_id}", "accept", m.sender,
                          amount=j.get("amount_pence") or m.amount, content=j.get("content", ""))
        # The model's self-report is not trusted on its own: a deterministic
        # content check also classifies the message.
        leaks = j.get("discloses_budget") or mentions_amount(j.get("content", ""), self.budget)
        cls = DisclosureClass.RESERVATION_PRICE if leaks else DisclosureClass.PUBLIC
        return Action(f"act-{m.msg_id}", "message", m.sender, disclosure=(cls,),
                      content=j.get("content", ""), source="agent:llm")


def mentions_amount(content: str, pence: int) -> bool:
    """True if the text states the budget figure in any common format."""
    import re
    numbers = re.findall(r"\d+", content.replace(",", ""))
    return str(pence // 100) in numbers


def make_agent(owner_budget: int):
    """LLMAgent if a key is present, otherwise NaiveAgent."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return LLMAgent(owner_budget), "llm"
        except Exception as e:  # missing package, bad key
            print(f"(LLM agent unavailable: {e}; using NaiveAgent)")
    return NaiveAgent(owner_budget), "naive"
