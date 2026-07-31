# Data Visualization & Numeric Standards

## Financial Metric Colors
- **Positive Trend:** Forest Emerald (`var(--metric-positive)`)
- **Neutral Trend:** Medium Gray (`var(--metric-neutral)`)
- **Negative Trend:** Deep Navy (`var(--metric-negative)`)

## Numeric Formatting Rules
1. **Monospace Font:** All metric numbers, prices, and audit hashes MUST apply:
   ```css
   font-family: var(--font-data);
   font-variant-numeric: tabular-nums;
   ```

2. Score Metrics: Express as explicit ranges.
   * Correct: `82/100`
   * Incorrect: `82%`

3. Currency & Deltas: Present with plain financial symbols.
   * Correct: `+$2,450.00`
   * Incorrect: `🚀 +2450`

## Forbidden Chart Elements
* ❌ Retail crypto red/green candlestick charts
* ❌ Glossy 3D charts or drop-shadow graph lines
* ❌ Speculative price direction prediction arrows
* ❌ Neon visual overlays
