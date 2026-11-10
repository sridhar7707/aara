# ADR-094: Price Feed Moves From yfinance to Alpaca; Reddit Sentiment Paused

**Status:** Accepted by the financial expert on the owner's delegation, 2026-11-09. Owner ratification pending. Implementation not started.
**Decision Type:** Data-source licensing decision (extends ADR-086). Touches frozen paths (`bot/`).
**Related:** ADR-086, ADR-087, ADR-089.

## Decision
1. **Price data:** move from yfinance to Alpaca's free market-data feed. Trigger: the written reply from Alpaca, or 2026-11-23 if there is no reply, whichever is first. Yahoo prohibits automated access regardless of the reply, so the switch does not wait beyond that date. IEX-only coverage is accepted for daily closes.
2. **Reddit sentiment:** pause it now. The WSB factor has no proven value, and Reddit's terms require a separate agreement for commercial purposes and research beyond the rate limits. Whether trading the owner's own account counts is for counsel. Resume only if counsel confirms, or a licence is signed.

## Reason
Both sources are used in a way their terms do not clearly permit, and neither has demonstrated predictive value in the trade record.

## Implementation (after ratification)
- Replace the yfinance price path with Alpaca bars, with tests against recorded data.
- Make the Reddit factor return a neutral value when paused, with one switch and a test.
- Compare the screener output before and after, and record the difference.

## Acceptance
Owner ratification required before the switch.

## Implementation status, 2026-11-09
- **Reddit pause: implemented.** `REDDIT_SENTIMENT_ENABLED` defaults to off. While off, `get_wsb_sentiment` returns a neutral value without reaching Reddit. Tests: `tests/test_reddit_pause.py`. Re-enable only after counsel confirms.
- **Price feed switch: not started.** Needs Alpaca bar code, tests against recorded data, and the screener comparison. Deadline: 2026-11-23, or earlier if Alpaca replies.
