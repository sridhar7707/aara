"""CSS for the Portfolio Intelligence screen -- MVP.

Design-system migration (Batch A): the colour `:root` entries below now
alias the shared `--aara-*` tokens from `ui/design_system.py` (the single
source of truth -- audit finding D-01). Each keeps its former hex as a
`var(--aara-*, <literal>)` fallback so a standalone
`PortfolioIntelligenceUI().build()` (no `bootstrap` composition) still
renders identically; the composed app resolves through the shared token.

Batch A also applies the shared numeric-alignment convention (audit finding
D-03) to this screen's three data tables -- right-aligning the numeric
columns, keeping the identifier/categorical columns left. Column indices
are this screen's own (see `_HOLDINGS_HEADERS` / `_ALPACA_POSITIONS_HEADERS`
/ `_ALPACA_ORDERS_HEADERS` in gradio_view.py); table *data* is unchanged.
"""

CSS = """
:root {
  --pi-color-navy: var(--aara-navy, #0B1F3A);
  --pi-color-gold: var(--aara-gold, #C8A45D);
  --pi-color-background: var(--aara-bg, #F8F7F3);
  --pi-color-surface: var(--aara-surface, #FFFFFF);
  --pi-color-text: var(--aara-text, #1A1A1A);
  --pi-color-text-secondary: var(--aara-text-muted, #666666);
  --pi-color-border: var(--aara-border, #E2E8F0);
  --pi-color-negative: var(--aara-negative-fg, #7A2E2E);
}

.gradio-container {
  background: var(--pi-color-background) !important;
}

/* Mirrors design_system.py's shared .aara-page-title primitive
   (identical values) so a standalone PortfolioIntelligenceUI().build()
   (no design_system.py loaded) still renders the same page title as the
   composed app. Normal-case, not uppercase/tracked (visual-quality pass,
   2026-09-17) -- see that primitive's own comment for why. */
.pi-page-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--pi-color-navy);
  margin: 0;
}
.pi-page-header .pi-subtitle {
  font-size: 14px;
  color: var(--pi-color-text-secondary);
  margin-top: 4px;
}

.pi-disclosure {
  border-left: 2px solid var(--pi-color-border);
  padding: 8px 0 8px 12px;
  margin: 8px 0;
}
.pi-disclosure-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--pi-color-text-secondary);
}
.pi-disclosure-body {
  font-size: 13px;
  font-style: italic;
  color: var(--pi-color-text-secondary);
}

.pi-section-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pi-color-text-secondary);
  margin: 16px 0 6px 0;
}

/* One-line source/scope caption under a section heading (e.g. Capital
   Summary's internal-ledger vs. Alpaca-account clarification). Same muted
   italic treatment as .pi-alpaca-orders-caption; sits directly under the
   uppercase section label, above that section's content. */
.pi-source-caption {
  font-size: 11px;
  font-style: italic;
  color: var(--pi-color-text-secondary);
  margin: -2px 0 6px 0;
}

.pi-capital-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px;
  background: var(--pi-color-surface);
  border: 1px solid var(--pi-color-border);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(11, 31, 58, 0.06);
}
.pi-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 120px;
}
.pi-metric-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--pi-color-text-secondary);
}
.pi-metric-value {
  font-size: 18px;
  font-weight: 700;
  font-family: Monaco, "Courier New", monospace;
  color: var(--pi-color-navy);
}
/* Impeccable critique finding #5: Realized Profit is the one capital
   metric that is a signed P&L figure -- a real loss gets the product's
   one restrained, desaturated negative token (already used in this same
   screen's Unrealized P&L chart, see _PNL_COLOR_MAP above) instead of the
   same navy every other capital metric uses. The $-prefixed sign in the
   text (e.g. "$-192.56") is unchanged and remains the primary signal;
   this is reinforcement, not the only cue. Only applied via the
   pi-metric-value--negative modifier gradio_view.py adds specifically to
   Realized Profit's own span -- every other capital metric keeps plain
   .pi-metric-value navy, since none of them can meaningfully be negative
   in this domain. */
.pi-metric-value--negative {
  color: var(--pi-color-negative);
}

.pi-allocation-bar {
  display: flex;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  border: 1px solid var(--pi-color-border);
}
.pi-allocation-bar .invested { background: var(--pi-color-navy); }
.pi-allocation-bar .cash { background: var(--pi-color-gold); }
.pi-allocation-legend {
  display: flex;
  gap: 16px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--pi-color-text-secondary);
}
.pi-allocation-legend .swatch {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 4px;
}
.pi-allocation-legend .invested .swatch { background: var(--pi-color-navy); }
.pi-allocation-legend .cash .swatch { background: var(--pi-color-gold); }

.pi-holdings-table table tbody td:first-child,
.pi-alpaca-positions-table table tbody td:first-child,
.pi-alpaca-orders-table table tbody td:first-child,
.pi-reconciliation-table table tbody td:first-child {
  font-weight: 600;
  color: var(--pi-color-navy);
}
.pi-holdings-table table tbody td,
.pi-alpaca-positions-table table tbody td,
.pi-alpaca-orders-table table tbody td,
.pi-reconciliation-table table tbody td {
  font-family: Monaco, "Courier New", monospace;
  font-variant-numeric: tabular-nums;
}

/* Numeric-column alignment (design-system convention D-03). Identifier and
   categorical columns keep the default left alignment; numeric columns are
   right-aligned so values line up on the decimal for column-down scanning.
   `th` is aligned to match its column. tabular-nums is already set above.
   Holdings:   Symbol | Quantity | Price | Market Value | Weight %
   Positions:  Symbol | Quantity | Avg Entry | Current Price | Market Value | Unrealized P/L | Unrealized P/L % | Side
   Orders:     Submitted | Symbol | Side | Type | Quantity | Filled Qty | Limit Price | Status | Working | Filled At */
.pi-holdings-table table thead th:nth-child(2),
.pi-holdings-table table thead th:nth-child(3),
.pi-holdings-table table thead th:nth-child(4),
.pi-holdings-table table thead th:nth-child(5),
.pi-holdings-table table tbody td:nth-child(2),
.pi-holdings-table table tbody td:nth-child(3),
.pi-holdings-table table tbody td:nth-child(4),
.pi-holdings-table table tbody td:nth-child(5) {
  text-align: right;
}
.pi-alpaca-positions-table table thead th:nth-child(2),
.pi-alpaca-positions-table table thead th:nth-child(3),
.pi-alpaca-positions-table table thead th:nth-child(4),
.pi-alpaca-positions-table table thead th:nth-child(5),
.pi-alpaca-positions-table table thead th:nth-child(6),
.pi-alpaca-positions-table table thead th:nth-child(7),
.pi-alpaca-positions-table table tbody td:nth-child(2),
.pi-alpaca-positions-table table tbody td:nth-child(3),
.pi-alpaca-positions-table table tbody td:nth-child(4),
.pi-alpaca-positions-table table tbody td:nth-child(5),
.pi-alpaca-positions-table table tbody td:nth-child(6),
.pi-alpaca-positions-table table tbody td:nth-child(7) {
  text-align: right;
}
.pi-alpaca-orders-table table thead th:nth-child(5),
.pi-alpaca-orders-table table thead th:nth-child(6),
.pi-alpaca-orders-table table thead th:nth-child(7),
.pi-alpaca-orders-table table tbody td:nth-child(5),
.pi-alpaca-orders-table table tbody td:nth-child(6),
.pi-alpaca-orders-table table tbody td:nth-child(7) {
  text-align: right;
}
/* Reconciliation: Symbol | Status | Internal Qty | Alpaca PAPER Qty |
   Qty Difference | Internal Market Value | Alpaca PAPER Market Value --
   only the numeric columns (3-7) are right-aligned; Status (2) stays
   left, same categorical-column convention as Side/Status above. */
.pi-reconciliation-table table thead th:nth-child(3),
.pi-reconciliation-table table thead th:nth-child(4),
.pi-reconciliation-table table thead th:nth-child(5),
.pi-reconciliation-table table thead th:nth-child(6),
.pi-reconciliation-table table thead th:nth-child(7),
.pi-reconciliation-table table tbody td:nth-child(3),
.pi-reconciliation-table table tbody td:nth-child(4),
.pi-reconciliation-table table tbody td:nth-child(5),
.pi-reconciliation-table table tbody td:nth-child(6),
.pi-reconciliation-table table tbody td:nth-child(7) {
  text-align: right;
}

/* Concise matched/different/internal-only/broker-only counts -- same
   factual-summary treatment as Performance & Learning's own .pl-summary,
   no new color/weight vocabulary. */
.pi-reconciliation-summary {
  font-size: 13px;
  color: var(--pi-color-text);
  margin: 2px 0 10px 0;
}

.pi-empty-message {
  font-size: 13px;
  font-style: italic;
  color: var(--pi-color-text-secondary);
  padding: 8px 0;
}

/* Visual Dashboard Phase A: the timeframe selector above the Portfolio
   Value Over Time chart. Gradio's own gr.Radio renders its choice pills;
   this only tightens spacing/type to sit calmly under the section label
   rather than styling the pills themselves. */
.pi-timeframe-selector {
  margin: 2px 0 10px 0;
}
.pi-timeframe-selector label {
  font-size: 12px;
}

/* Alpaca Paper sections (broker-side observation, separate from the
   bot's own capital/holdings). The badge must stay unmistakable as
   paper/sandbox data; unavailable state must stay visually distinct
   from any populated state. */
.pi-alpaca-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--pi-color-gold);
  color: var(--pi-color-navy);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  vertical-align: middle;
}
.pi-unavailable,
.pi-alpaca-unavailable {
  font-size: 13px;
  font-style: italic;
  color: var(--pi-color-text-secondary);
  border-left: 2px solid var(--pi-color-border);
  padding: 8px 0 8px 12px;
  margin: 4px 0;
}
.pi-alpaca-orders-truncation,
.pi-alpaca-orders-caption {
  font-size: 11px;
  font-style: italic;
  color: var(--pi-color-text-secondary);
  padding: 4px 0;
}

.pi-portfolio-history-chart {
  margin: 4px 0;
}

/* Visual Dashboard Phase B: drawdown chart, directly below the value
   chart -- same minimal spacing rule, no new visual language. */
.pi-portfolio-drawdown-chart {
  margin: 4px 0;
}

/* Visual Dashboard Phase B: allocation-by-holding bars -- same visual
   language as .pi-allocation-bar above (navy fill on a bordered track),
   one row per holding instead of two fixed segments. */
.pi-holding-allocation-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pi-holding-allocation-row {
  display: grid;
  grid-template-columns: 64px 1fr 52px;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
.pi-holding-allocation-symbol {
  font-weight: 600;
  color: var(--pi-color-navy);
}
.pi-holding-allocation-bar {
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  border: 1px solid var(--pi-color-border);
}
.pi-holding-allocation-bar .fill {
  background: var(--pi-color-navy);
  height: 100%;
}
.pi-holding-allocation-pct {
  font-family: Monaco, "Courier New", monospace;
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: var(--pi-color-text);
}
"""
