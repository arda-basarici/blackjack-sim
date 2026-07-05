# Blackjack Monte Carlo Simulator

**Build the data source first, then analyze it** — a from-scratch, self-validating blackjack
engine, and a statistical study of what optimal play, bet sizing, and card counting actually
buy, measured over ~90 million simulated hands.

The engine is configurable (casino rule presets, pluggable strategies and counting systems,
per-decision data recording) and *self-validating*: blackjack has published ground truth, and
the engine's measured basic-strategy house edge of **0.45%** lands on it. That validated anchor
is why the sequel project — [blackjack-rl](https://github.com/arda-basarici/blackjack-rl), an
RL audit study — could consume this engine read-only as its measurement instrument.

> A research/portfolio project. The goal was never to beat the casino; it is the full pipeline —
> design → simulate → validate → analyze → report — with every number regenerable from a seed.

---

## Findings

Full analysis with charts: [blackjack_analysis_report.pdf](blackjack_analysis_report.pdf) ·
notebooks in [`analysis/`](analysis/).

- **Basic strategy cuts the house edge from 45.8% (random) to 0.45%** — a ~45-point swing from
  specific, identifiable decisions: doubling 9–11 against a weak dealer, standing 12–16 against
  dealer 2–6, correct splits.
- **Avoiding busts is not the goal — expected value is.** Semi-Random has the *lowest* bust rate
  of all strategies (12.4% vs Basic's 15.8%) and a 12× worse edge: it trades busts for standing
  losses.
- **Betting systems change variance, not expected value.** Martingale ruins 40.1% of sessions vs
  flat betting's 1.0%, with no better average net — the casino's edge is invariant to bet-sizing
  patterns.
- **The information is the edge, not the pattern.** Count-based betting with no counting system
  attached is identical to flat betting.
- **Counting works — and the conditions dominate.** Only single-deck play with index deviations
  produces a real player edge, and the same aggressive spread that creates it drives the risk:

| Configuration (10,000 sessions × 1,000 hands, seed 42) | Avg net / 1000 hands | Ruin rate |
| --- | --- | --- |
| Basic + flat bet (baseline) | −$45 | 1.0% |
| Basic + count betting, Hi-Lo, 6 decks | −$12 | 6.6% |
| Counting strategy + count betting, Hi-Lo, 6 decks | −$5 | 6.5% |
| Basic + count betting, Hi-Lo, single deck | +$216 | 22.1% |
| **Counting strategy + count betting, Hi-Lo, single deck** | **+$314** | **20.4%** |

  Expected value and risk of ruin are **independent levers** — the best-EV configuration goes
  broke in one session of five. Profit is not survival. (Comparisons use net dollars, not
  return-on-bankroll: counters wager 2–2.4× more, so rate-of-return figures flatter them.)

## What it demonstrates

Measurement discipline on a domain with known ground truth: validation against published
numbers, one seed and stable named runs (every table above is regenerable by one command),
baselines under every claim, and honest metric choice (edge per dollar wagered, ruin reported
beside EV, never collapsed into one number).

---

## Run it

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev,report]

python -m pytest -q                    # the test suite

# Run basic strategy, 100k hands
python main.py --mode hands --strategy basic --config vegas --hands 100000

# A session experiment: basic play, martingale betting
python main.py --mode sessions --strategy basic --betting martingale --config vegas --hands 1000 --sessions 1000

# Card counting on single deck (betting flags matter only in sessions mode)
python main.py --mode hands --strategy counting --counting hilo --config single --hands 100000

# Regenerate every run the notebooks and report use (13 runs, ~90M hands, seed 42)
python regenerate_data.py              # or --quick for a fast sanity check

python generate_report.py              # rebuild the PDF report from the run data
```

## Layout

| where | what |
| --- | --- |
| `simulator/` | the engine: cards/deck, counting systems, hand logic, the `GameState` contract, hand & session simulators |
| `strategies/` | the pluggable players: basic strategy, Illustrious-18 counting, baselines; flat / martingale / count-based betting |
| `experiments/` | the experiment runner — named runs to `data/runs/` (CSV + metadata) |
| `analysis/` | the two analysis notebooks (hand-level, session-level) |
| `tests/` | 83 tests: hand logic, counting systems, contracts, rules regressions |
| `main.py` · `regenerate_data.py` · `generate_report.py` | CLI entry point · one-command data regeneration · the PDF report |

## Scope & limits

- Simulation only, one game family: no insurance, one player seat, surrender only on the
  opening two cards. Intentional simplifications are documented in
  [ARCHITECTURE.md](ARCHITECTURE.md).
- Session numbers are for the stated stakes ($1,000 bankroll, $10 base bet); the *relationships*
  (variance-not-EV, edge-vs-ruin) are the findings, not the dollar figures.
- Statistical claims are point estimates at large samples; confidence intervals arrived in the
  successor project's methodology, not here.

## Deeper

[DESIGN.md](DESIGN.md) — the decisions and why · [ARCHITECTURE.md](ARCHITECTURE.md) — the
structure, and the correctness audit that earned the "validated" label ·
[blackjack_analysis_report.pdf](blackjack_analysis_report.pdf) — the full analysis.
