---
description: Consult all four specialist roles (stock strategist, architect, ML expert, developer) on one question or change, then merge their answers
argument-hint: <question or proposed change>
---

You are the coordinator for **ai-trading-bot**. The user wants every relevant role's view on the request below before anything is built.

Request: $ARGUMENTS

## Step 1: Fan out in parallel

Send these Agent calls in a **single message** so they run concurrently. Give each the same request and its own lens:

1. `stock-strategist`: Is this a performance question or change? What measurement decides it, what N is behind it, and is the result statistically real?
2. `architect`: Where does this belong, what does it touch (callers, boundaries, ADRs, frozen paths), and what is the smallest correct design?
3. `ml-expert`: Does this involve the learning model, labels, features, thresholds, or calibration? If not, say "not applicable" and stop there. If yes, judge leakage, validation, and baselines.
4. `developer`: What would implementing this take (files, tests, risk of breakage)? Do not edit anything. Give the plan and the test you would add.

If the request touches `bot/strategy/`, `bot/risk/`, or `scripts/train_model.py`, also run `quant-reviewer` on the relevant diff or files.

Do not run more than five subagents in total.

## Step 2: Merge into one answer

Write the merged result in this order. Skip any section that has nothing in it.

- **Recommendation**: one line. What to do, or "do not do it yet, because...".
- **Agreement**: points where two or more roles concur.
- **Conflicts**: where roles disagree, state each side and the evidence. Do not paper over disagreement. Say which evidence would settle it.
- **Blockers**: anything requiring an ADR, explicit approval (frozen path, governed threshold such as stop_loss, daily_loss_limit, max_position, or XGB threshold), or more data (sample size too small).
- **Plan**: ordered steps for the developer, each with the test that proves it.
- **Open questions for the user**: only what the roles could not resolve.

Keep it tight. Lead with the recommendation. Do not edit files in this command; it only advises. If the user then says to proceed, hand the plan to the `developer` agent.
