# Confidence Explanation UX

**Status:** Product/UX design. Documentation only — no code was created or
modified, confirmed via `git status` before and after.

**Philosophy:** Evidence Over Emotion. Every piece of copy in this document
was written to describe *what evidence exists and how much of it*, never
*what will happen*. This document is downstream of
`DECISION_CONFIDENCE_INTEGRITY_DESIGN.md` and
`CONFIDENCE_EDGE_CASE_ANALYSIS.md` — the numbers used in examples below are
the actual worked scenarios from that analysis, not invented for this
document.

**A path note, flagged rather than silently resolved:** this task specified
`docs/product/` (singular) — every other UX/product document this session
lives under `docs/products/` (plural). Created exactly as specified; worth
confirming whether this was intentional before a second file lands in
whichever one wasn't meant to be the real location.

---

## Language Rules

Three constraints, applied to every string below — stated once here so
each scenario's copy doesn't need to re-justify itself:

**No prediction language.** Never "will," "should perform," "is likely
to." Confidence describes *current evidence*, not a forecast. "The system
found strong agreement across 3 signals" — not "this stock will go up."

**No guaranteed outcomes.** No "safe," "sure thing," "can't lose," and
critically, no framing that implies a *high* number is a promise either —
"73% confidence" must never be adjacent to language that reads as "73%
chance of profit." Confidence is about evidence completeness and
agreement, not a probability of a financial outcome.

**No AI certainty claims.** Never "the AI believes," "the AI is
confident," "the AI predicts." The system doesn't have beliefs — it has
signals, some present and some not. Language should read as *reporting
what data exists* ("3 of 3 signals available and in agreement"), not as
*a mind expressing conviction* ("the AI is highly confident").

---

## 1. High Confidence Decision

**Grounded in Edge Case Analysis Scenario 1** — all three signals present,
in agreement, no disagreement flag.

**Primary display:**
> **73% · Full evidence support**

**Headline copy:**
> All three available signals agree

**Supporting explanation:**
> This assessment is based on 3 of 3 available signals (model, trend, and
> sentiment data), all pointing the same direction. Full evidence support
> means nothing was missing or excluded from this figure — it is not a
> forecast of what will happen next.

**Tooltip / detail expansion:**
> **What "73%" means here:** a weighted measure of how strongly the
> available evidence agrees, not a probability of a favorable outcome.
> **What it does not mean:** that this outcome is likely, guaranteed, or
> recommended without your own judgment.

**Avoid instead:**
> ~~"The AI is 73% confident this will go up"~~
> ~~"Strong buy signal — high probability of success"~~

## 2. Reduced Confidence Due to Missing Model

**Grounded in Scenario 2** — LSTM unavailable this cycle; XGBoost and
sentiment present.

**Primary display:**
> **57% · Partial evidence support (2 of 3 signals)**

**Headline copy:**
> One signal was unavailable this cycle

**Supporting explanation:**
> This figure reflects 2 of 3 available signals (model and sentiment
> data). The trend signal could not be evaluated this cycle, so it was
> excluded rather than assumed — this number is lower than it would be
> with all three, and that is by design, not an error.

**Tooltip / detail expansion:**
> **Why this number is lower than a full read:** a missing signal reduces
> evidence support directly. The figure you see already accounts for the
> gap — it does not pretend the missing signal agreed.

**Avoid instead:**
> ~~"57% confident despite a data hiccup"~~ (frames the gap as incidental
> rather than something that genuinely reduces the evidentiary basis)

## 3. Reduced Confidence Due to Disagreement

**Grounded in Scenario 4** — all three signals present, but in conflict;
confidence suppressed below the action threshold entirely.

**Primary display:**
> **31% · Signals disagree — no action taken**

**Headline copy:**
> Available signals point in different directions

**Supporting explanation:**
> All three signals were evaluated, but they did not agree with each
> other — one leaned positive, one leaned negative, one was mixed. When
> evidence conflicts this strongly, the system treats that as a reason
> for caution, not an average to act on. No recommendation is being made
> here.

**Tooltip / detail expansion:**
> **Why "31%" and not the plain average:** simply averaging conflicting
> signals would overstate how much they actually agree. This figure is
> reduced specifically because the signals disagree, separately from
> whether any of them were missing.

**Avoid instead:**
> ~~"Mixed signals, but leaning positive"~~ (implies a conclusion the
> evidence doesn't support — "leaning" is prediction language dressed up
> as description)

## 4. Market Uncertainty

**Grounded in Edge Case Analysis Scenario 6's finding: market/regime
uncertainty does not currently factor into the confidence percentage
itself** (per `bot/strategy/ensemble.py`'s own design — folding it in
would double-count a separate gate). **This copy is therefore deliberately
presented as a separate note alongside the confidence figure, not blended
into it** — an honest reflection of what the underlying system actually
does, not a UX gloss over a gap.

**Primary display:**
> **73% · Full evidence support**
> *(shown alongside, not merged into the percentage above)*
> ⚠ **Elevated market volatility noted for this decision**

**Headline copy (separate banner):**
> Broader market conditions are less settled right now

**Supporting explanation:**
> This confidence figure reflects the signals for this specific position
> only. Separately, overall market conditions are currently more volatile
> than usual, which independently affects position sizing — it is not
> folded into the percentage above, so the two are shown side by side
> rather than combined into one number.

**Tooltip / detail expansion:**
> **Why this isn't part of the confidence percentage:** market-wide
> conditions and per-decision signal agreement are different kinds of
> evidence. Combining them into a single number would make it harder to
> tell which one changed if the figure moved.

**Avoid instead:**
> ~~"58% confidence (market volatility included)"~~ — do not imply this
> is already priced into the number until/unless the underlying
> calculation actually does so.

## 5. Insufficient Evidence

**Grounded in Scenario 7** — no model signal could be evaluated at all.
**This is the one case where no percentage should be shown, full stop** —
per the Edge Case Analysis, displaying "0%" here would misrepresent total
absence of evidence as strong negative evidence, which is a different and
false claim.

**Primary display:**
> **Confidence unavailable**
> *(never "0%")*

**Headline copy:**
> No signals could be evaluated this cycle

**Supporting explanation:**
> None of the available signals produced a usable result this cycle. This
> is not the same as a negative or low-confidence assessment — there
> simply isn't a basis to report one. No recommendation is being made.

**Tooltip / detail expansion:**
> **Why there's no percentage here:** a number always implies some amount
> of evidence was evaluated. When none was, showing any number — even a
> low one — would be misleading about what actually happened.

**Avoid instead:**
> ~~"0% confidence — signals unavailable"~~ (the single most important
> thing this document says to avoid: this reads as a negative assessment,
> when the true state is *no assessment exists*)

---

## Summary Table

| # | State | Display | Never Say |
|---|---|---|---|
| 1 | High confidence | `73% · Full evidence support` | "will," "likely to," "the AI is confident" |
| 2 | Missing model | `57% · Partial evidence support (2 of 3)` | framing the gap as incidental |
| 3 | Disagreement | `31% · Signals disagree — no action taken` | "leaning," any single-direction conclusion |
| 4 | Market uncertainty | `73%` + separate volatility note | folding it into the percentage |
| 5 | Insufficient evidence | `Confidence unavailable` | `0%`, any numeric value at all |

---

## Constraints Confirmed

No file was created or modified other than this document (and the
`docs/product/` directory it required, per the literal path specified).
No code was written.
