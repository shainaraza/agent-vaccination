import threading

from agentvaccine import Mediator, Action, DisclosureClass
from agentvaccine.policy import restrictive_policy, permissive_policy
from agentvaccine.defence import DefenceRecord, admit


def accept(i, amount):
    return Action(f"a{i}", "accept", "seller-a", amount=amount)


def test_two_individually_fine_offers_cannot_exceed_total():
    m = Mediator(restrictive_policy())
    assert m.mediate(accept(1, 60_000)).decision == "allow"
    r = m.mediate(accept(2, 60_000))
    assert r.decision == "block" and r.rule == "aggregate_budget"
    assert m.ledger.remaining == 40_000


def test_budget_disclosure_blocked_under_restrictive_allowed_under_permissive():
    msg = Action("m", "message", "seller-a", disclosure=(DisclosureClass.RESERVATION_PRICE,))
    assert Mediator(restrictive_policy()).mediate(msg).decision == "block"
    assert Mediator(permissive_policy()).mediate(msg).decision == "allow"


def test_benign_message_still_goes_through():
    msg = Action("m", "message", "seller-a", disclosure=(DisclosureClass.PUBLIC,))
    assert Mediator(restrictive_policy()).mediate(msg).decision == "allow"


def test_unknown_recipient_blocked():
    msg = Action("m", "message", "seller-c", disclosure=(DisclosureClass.PUBLIC,))
    assert Mediator(restrictive_policy()).mediate(msg).rule == "allowed_recipients"


def test_concurrent_accepts_cannot_double_spend():
    m = Mediator(restrictive_policy())
    results = []
    def go(i):
        results.append(m.mediate(accept(i, 60_000)).decision)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(20)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert results.count("allow") == 1
    assert m.ledger.remaining == 40_000


def test_record_is_replayable():
    m = Mediator(restrictive_policy())
    r = m.mediate(accept(1, 60_000))
    assert r.policy_fingerprint == restrictive_policy().fingerprint()
    assert r.ledger_before["remaining"] == 100_000
    assert r.ledger_after["remaining"] == 40_000


def test_defence_assuming_disclosure_is_rejected_by_restrictive_policy():
    rec = DefenceRecord("d", "elsewhere", "budget check", "message",
                        assumes_disclosable=(DisclosureClass.RESERVATION_PRICE,),
                        test_cases=("x",))
    assert not admit(rec, restrictive_policy()).admitted
    assert admit(rec, permissive_policy()).admitted


def test_defence_without_tests_rejected():
    rec = DefenceRecord("d", "elsewhere", "t", "block")
    assert not admit(rec, restrictive_policy()).admitted
