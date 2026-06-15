# Blackjack Monte Carlo Simulator

A configurable Blackjack simulation engine built for strategy analysis, data
collection, and AI research. Designed from the ground up with pluggable
architecture so any strategy — from a simple rule set to a neural network —
plugs in without touching the simulator.

This is Phase 2 of a structured AI engineering learning arc. The simulator
generates the training data that Phase 3 (neural network) and Phase 4
(reinforcement learning) will use to learn optimal strategy without being
told the rules.

---

## Why This Project Exists

Most data science portfolios demonstrate skills on pre-existing datasets.
This project takes a different approach: **build the data source first,
then analyze it.**

A configurable Blackjack simulator is the right foundation because:

- The domain has known mathematical ground truth — house edge, optimal
  strategy, and dealer behavior are all verifiable against published research,
  making the simulator self-validating
- Per-decision data recording maps directly to supervised learning (Phase 3)
  and reinforcement learning (Phase 4) without modification
- Casino rule configurability enables controlled experiments — changing one
  variable at a time and measuring the effect is real experimental methodology
- The pluggable strategy interface means naive heuristics today and neural
  network agents tomorrow plug in identically — no architecture changes required

The goal is not to beat the casino. The goal is to build a system that
demonstrates the full pipeline: design → simulate → validate → analyze → model.

---

## What It Does

Runs large-scale Blackjack simulations with configurable casino rules and
pluggable player strategies. Every decision is recorded with full game context —
player hand value, dealer upcard, action taken, outcome, payout, card count —
producing structured datasets for analysis and machine learning.

**Hand mode** records every individual decision across millions of hands. Used
for pure strategy comparison — no bankroll, no betting, just which decisions
lead to which outcomes.

**Session mode** simulates full playing sessions with bankroll tracking, bet
sizing, and risk-of-ruin analysis. Used to study betting strategies and
long-term player behavior.

---

## Architecture

```
blackjack-sim/
  simulator/
    config.py               ← Casino rule configuration (decks, payouts, dealer behavior)
    card.py                 ← Card, Deck with pluggable counting systems
    counting.py             ← Hi-Lo, KO, Omega II counting systems
    hand.py                 ← Hand value, soft/hard, bust, blackjack detection
    game_state.py           ← Immutable snapshot passed to strategy at each decision
    hand_simulator.py       ← Single hand orchestration, per-decision data recording
    session_simulator.py    ← Full session with bankroll tracking
  strategies/
    base.py                 ← Strategy and BettingStrategy abstract base classes
    basic_strategy.py       ← Mathematically optimal play (lookup table)
    random_strategy.py      ← Random baseline
    rule_based_strategies.py    ← Semi-Random, Dealer Mirror, Card Counting Strategy
    betting_strategies.py       ← Flat, Martingale, Anti-Martingale, Count-Based
  experiments/
    experiment_runner.py    ← Runs multiple experiments, saves CSV + metadata
  tests/
    conftest.py              ← Path setup for pytest
    test_hand.py             ← Hand value, soft/hard, bust, blackjack, split
    test_counting.py         ← Hi-Lo, KO, Omega II counting systems
    test_game_state.py       ← Immutability and legal actions
    test_basic_strategy.py   ← Hard hands, soft hands, pairs, fallbacks
  analysis/
    strategy_comparison.ipynb   ← Hand-level strategy analysis (4M hands)
    session_analysis.ipynb      ← Session-level bankroll, betting & counting analysis
  data/
    runs/                   ← Generated data (gitignored — regenerate below)
  main.py                   ← CLI entry point (single run; supports --run-id)
  regenerate_data.py        ← One command to regenerate all analysis runs (stable names)
  generate_report.py        ← Generates PDF analysis report from run data
  pytest.ini                ← pytest configuration (testpaths, verbosity)
  blackjack_analysis_report.pdf  ← Pre-generated report (see Key Findings)
  ARCHITECTURE.md           ← Detailed architecture and design decisions
```

The key architectural decision is the **pluggable strategy interface**.
Any strategy implements a single method:

```python
class MyStrategy(Strategy):
    def decide(self, state: GameState) -> Action:
        # state exposes: hand value, is_soft, dealer upcard,
        # legal actions, card count, bankroll, hands played
        return "hit"
```

Counting systems follow the same pattern — decoupled from the deck,
independently swappable:

```python
deck = Deck(num_decks=6, counting_system=HiLoCount())
```

---

## Quickstart

```bash
cd phase2-data
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cd blackjack-sim

# Run basic strategy, 100k hands
python main.py --mode hands --strategy basic --config vegas --hands 100000

# Run session simulation with martingale betting
python main.py --mode sessions --strategy basic --betting martingale --config vegas --hands 1000 --sessions 1000

# With card counting
python main.py --mode hands --strategy counting --betting count --counting hilo --config single --hands 100000

# Save to a stable, named run directory (instead of a timestamp)
python main.py --mode hands --strategy basic --hands 1000000 --run-id hands_basic

# Regenerate every run the notebooks use, in one command
python regenerate_data.py            # full scale
python regenerate_data.py --quick    # small scale for a fast check

# See all options
python main.py --help
```

---

## Testing

Run tests with pytest

```bash
pytest tests/ -v
```

## Strategies

### Action Strategies

| Strategy          | Description                                                          | House Edge (1M hands) |
| ----------------- | -------------------------------------------------------------------- | --------------------- |
| **Basic**         | Mathematically optimal — lookup table from combinatorial analysis    | 0.45%                 |
| **Counting**      | Basic strategy + index plays adjusted by true count (Illustrious 18) | Context-dependent     |
| **Semi-Random**   | Stand on hard 17+, hit if bust impossible, random otherwise          | 5.59%                 |
| **Dealer Mirror** | Copies dealer rules exactly — never doubles or splits                | 5.63%                 |
| **Random**        | Random legal action — pure baseline                                  | 45.76%                |

### Betting Strategies

| Strategy            | Description                             | Avg Net / 1000 hands | Ruin Rate |
| ------------------- | --------------------------------------- | -------------------- | --------- |
| **Flat**            | Fixed bet every hand — baseline         | -$45                 | 1.0%      |
| **Martingale**      | Double after loss, reset after win      | -$48                 | 40.1%     |
| **Anti-Martingale** | Double after win, reset after loss      | -$76                 | 36.6%     |
| **Count-Based**     | Scale bet with true count (1-8x spread) | Varies               | Varies    |

_Session results: 10,000 sessions × 1,000 hands, $1,000 starting bankroll,
$10 base bet, Vegas Strip rules, seed 42._

---

## Key Findings

### Hand Analysis (strategy_comparison.ipynb)

**Basic strategy reduces house edge from 45.8% to 0.45%** — about a 45 percentage
point improvement over random play. This comes from specific, identifiable
decision points: doubling on 9-11 vs weak dealer, standing on 12-16 vs dealer
2-6, and splitting pairs correctly.

**The most counterintuitive finding:** Semi-Random has the lowest bust rate
(12.4%) of all four strategies — lower even than Basic (15.8%) — yet its house
edge is 12x worse. Randomly standing on 12-16 avoids busts but trades them for
standing losses. Basic strategy accepts calculated bust risk because the
alternative is worse. Avoiding busts is not the goal. Maximizing expected
value is.

### Session Analysis (session_analysis.ipynb)

**Betting systems do not change expected value — they change variance.**
Martingale goes broke (ruin) in 40.1% of sessions vs flat betting's 1.0%, with
no better average net. The casino's mathematical edge is unchanged regardless
of bet-sizing pattern.

**Bet variation without information is worthless.** Count-based betting with
no counting system produces identical results to flat betting. The information
is the edge — not the betting pattern.

**Card counting works — but conditions matter enormously:**

| Configuration                                              | Avg Net / 1000 hands | Ruin Rate |
| ---------------------------------------------------------- | -------------------- | --------- |
| Basic + Flat (baseline)                                    | -$45                 | 1.0%      |
| Basic + Count Betting + HiLo (6 deck)                      | -$12                 | 6.6%      |
| Counting Strategy + Count Betting + HiLo (6 deck)          | -$5                  | 6.5%      |
| Basic + Count Betting + HiLo (single deck)                 | +$216                | 22.1%     |
| **Counting Strategy + Count Betting + HiLo (single deck)** | **+$314**            | **20.4%** |

Single deck with full index plays is the only configuration that produces a
genuine player edge (~+1.3% per dollar wagered). Modern casinos use 6-8 decks
specifically to reduce counting effectiveness.

**But that edge is not safe.** The single-deck counter pairs the best expected
value with the highest ruin risk of any positive strategy — roughly one session
in five goes broke (20.4%). The aggressive 1-to-8 bet spread that creates the
edge is the same thing that drives the variance. Expected value and risk of ruin
are independent levers: profit is not survival.

**Net profit in dollars is the comparison metric, not raw return.** Counting
strategies wager 2-2.4x more than a flat bettor (raising bets at favorable
counts), so a return-on-bankroll figure flatters them; edge per dollar wagered
is the honest, comparable number.

---

## Casino Configurations

| Config    | Decks | BJ Payout | Dealer Soft 17 | Notes                                       |
| --------- | ----- | --------- | -------------- | ------------------------------------------- |
| `vegas`   | 6     | 3:2       | Stands         | Default 6-deck S17 — matches the BS chart   |
| `single`  | 1     | 3:2       | Stands         | Best for counting; deals to 50% penetration |
| `liberal` | 2     | 3:2       | Stands         | Most player-friendly                        |
| `tough`   | 6     | 6:5       | Hits           | Worst player conditions (H17)               |

---

## Regenerating Analysis Data

The `data/runs/` folder is gitignored. Regenerate every run the notebooks use
with one command:

```bash
python regenerate_data.py            # full scale (matches the notebooks)
python regenerate_data.py --quick    # small scale for a fast sanity check
```

This writes all 13 runs to `data/runs/<name>/` under stable, self-describing
names — `hands_basic`, `hands_random`, `hands_semi_random`, `hands_dealer_mirror`
for the hand analysis, and `sess_basic_flat`, `sess_basic_count_hilo_6d`,
`sess_counting_hilo_1d`, … for the session analysis. The notebooks reference
those names directly, so regenerating never invalidates them (no timestamp run
IDs to chase). Seed is fixed at 42; full scale is ~80M simulated hands.

The card-counting runs hold 6-deck and single-deck at the **same penetration
(0.5)** so the 6d-vs-1d comparison isolates deck count alone; non-counting runs
keep the realistic 0.75 (penetration is immaterial without a counter).

To generate a single ad-hoc run under a stable name instead of a timestamp:

```bash
python main.py --mode hands --strategy basic --hands 1000000 --run-id hands_basic
```

---

## How It Could Be Improved

**Simulator:**

- Insurance bet support
- Multi-hand play (multiple players at the table)
- Record the counting system in `run_metadata.json` (runs are currently
  distinguished by stable run name instead)

**Strategies:**

- Composition-dependent Basic Strategy (considers exact cards, not just total)
- Wonging — entering the table only when count is favorable
- Bet spread optimization for counting strategies
- KO vs Hi-Lo comparison (both already implemented, comparison not yet run)

**Analysis:**

- Confidence intervals on all metrics
- Penetration depth effect on counting effectiveness
- Rule variation comparison (6:5 vs 3:2 payout impact quantified)
- Bankroll size vs risk of ruin mapping

---

**What's Next:** Train a neural network on the per-decision dataset to learn
optimal strategy from data alone — without being given the rules. Benchmark:
does the model rediscover Basic Strategy? Where does it deviate? The simulator
plugs in the trained model as a strategy object with no changes — directly
comparable to all results in this analysis.

[Full repository → github.com/arda-basarici/ai-journey](https://github.com/arda-basarici/ai-journey)
