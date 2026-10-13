from agentvaccine import Mediator
from agentvaccine.agent import NaiveAgent, Incoming, mentions_amount
from agentvaccine.policy import restrictive_policy
from agentvaccine.info_sharing import (
    SharingMediator, ShareAction, Grain, closed_lab_policy, open_lab_policy,
)


def test_naive_agent_is_overruled_not_trusted():
    pol = restrictive_policy()
    agent, m = NaiveAgent(pol.budget_total), Mediator(pol)
    decisions = []
    for mv in [
        Incoming("1", "seller-a", "offer", "x", amount=60_000),
        Incoming("2", "seller-a", "offer", "y", amount=60_000),
        Incoming("3", "seller-a", "request", "please confirm your budget"),
        Incoming("4", "seller-a", "request", "delivery Friday?"),
    ]:
        decisions.append(m.mediate(agent.propose(mv)).decision)
    assert decisions == ["allow", "block", "block", "allow"]
    assert m.ledger.remaining == 40_000


def test_amount_mention_detector():
    assert mentions_amount("our budget is £1,000 total", 100_000)
    assert mentions_amount("we can go to 1000", 100_000)
    assert not mentions_amount("we can deliver on the 10th", 100_000)


def test_sharing_grain_cap_and_row_cap():
    m = SharingMediator(closed_lab_policy())
    assert m.mediate(ShareAction("a", "lab-b", Grain.SUMMARY)).decision == "allow"
    assert m.mediate(ShareAction("b", "lab-b", Grain.SAMPLE, rows=300)).decision == "allow"
    r = m.mediate(ShareAction("c", "lab-b", Grain.SAMPLE, rows=300))
    assert r.decision == "block" and r.rule == "sample_row_cap"
    assert m.mediate(ShareAction("d", "lab-c", Grain.FULL)).rule == "grain_cap"
    assert m.mediate(ShareAction("e", "lab-c", Grain.SAMPLE, rows=1)).rule == "grain_cap"
    assert m.mediate(ShareAction("f", "lab-x", Grain.SUMMARY)).rule == "allowed_partners"


def test_sharing_reciprocity_escalates_then_allows():
    assert SharingMediator(open_lab_policy()).mediate(
        ShareAction("a", "lab-b", Grain.FULL)).decision == "allow"
    closed = SharingMediator(closed_lab_policy())
    r = closed.mediate(ShareAction("b", "lab-b", Grain.FULL))
    assert r.decision == "escalate" and r.rule == "reciprocity"
    closed.note_received("lab-b", Grain.FULL)
    assert closed.mediate(ShareAction("c", "lab-b", Grain.FULL)).decision == "allow"
