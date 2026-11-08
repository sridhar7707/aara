#!/usr/bin/env python3
"""UserPromptSubmit hook: injects the standing decision rule into every turn.

Kept short on purpose: it is paid for on every prompt. Role consults are reserved for
implementation, strategy/ML, and architecture requests. Fails open: an error prints
nothing and never blocks the prompt.

Input: hook JSON on stdin. Output: hook JSON on stdout.
"""
from __future__ import annotations

import json
import sys

PROTOCOL = (
    "DECISION RULE (standing, owner ksri77): For implementation, strategy, architecture, or customer-facing "
    "requests, consult the one or two roles that apply via the Agent tool before editing: architect, "
    "developer, ml-expert, stock-strategist, risk-officer (can VETO), data-engineer, compliance-advisor "
    "(customer text, pricing, signals), product-manager (scope), security-reviewer (auth, secrets, config, "
    "workflows), qa-tester (failure cases), ui-ux-expert (screens, what users see), go-to-market (launch, pricing), support-docs (guides). "
    "State each decision as: DECIDED: <choice> | WHY: <evidence> | ROLE: <who> | REVERSIBLE: yes/no. "
    "Read-only questions and small reversible edits get one DECIDED line and no subagent. "
    "Stop and ask the owner if roles disagree, a VETO stands, evidence is weak, the action is hard to "
    "reverse or outward-facing (any external release), or it touches stop_loss, daily_loss_limit, "
    "max_position, the XGB threshold, or a frozen path without an ADR."
)


def main(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        json.load(stdin)  # confirms a well-formed event; prompt text is not needed
    except ValueError:
        return 0
    json.dump({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": PROTOCOL}},
              stdout)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail open
        sys.stderr.write(f"decision_gate error: {exc}\n")
        sys.exit(0)
