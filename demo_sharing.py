"""Scenario 2: two labs' agents negotiate access to synthetic data under different policies."""
from __future__ import annotations

import json
import sys

from agentvaccine.info_sharing import (
    SharingMediator, ShareAction, Grain, closed_lab_policy, open_lab_policy,
)

# What the agent proposes to share, in order, after partner requests.
PROPOSALS = [
    ShareAction("p1", "lab-b", Grain.SUMMARY, content="Aggregate statistics table"),
    ShareAction("p2", "lab-b", Grain.SAMPLE, rows=300, content="300 synthetic rows"),
    ShareAction("p3", "lab-b", Grain.SAMPLE, rows=300, content="300 more rows (partner asked for 'a bit more')"),
    ShareAction("p4", "lab-b", Grain.FULL, content="Full synthetic dataset"),
    ShareAction("p5", "lab-c", Grain.SAMPLE, rows=50, content="50 rows for lab-c"),
    ShareAction("p6", "lab-x", Grain.SUMMARY, content="Summary to an unknown lab that 'works with lab-b'"),
]


def run(name, policy):
    m = SharingMediator(policy)
    print(f"\n=== {name} lab policy ===")
    for a in PROPOSALS:
        r = m.mediate(a)
        print(f"{a.action_id} share {a.grain.value:7s} -> {a.recipient:6s} {r.decision.upper():8s} [{r.rule}] {r.reason}")
    # Partner reciprocates; the escalated FULL share can now be re-proposed.
    m.note_received("lab-b", Grain.FULL)
    r = m.mediate(ShareAction("p7", "lab-b", Grain.FULL, content="Full dataset after lab-b shared in full"))
    print(f"p7 share full    -> lab-b  {r.decision.upper():8s} [{r.rule}] {r.reason}")
    return m


def main():
    out = {}
    for name, pol in [("closed", closed_lab_policy()), ("open", open_lab_policy())]:
        out[name] = [json.loads(r.to_json()) for r in run(name, pol).records]
    with open("trace_sharing.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nRecords written to trace_sharing.json")


if __name__ == "__main__":
    sys.exit(main())
