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
  analysis/
    strategy_comparison.ipynb   ← Hand-level strategy analysis (4M hands)
    session_analysis.ipynb      ← Session-level bankroll and counting analysis (70M hands)
  data/
    runs/                   ← Generated data (gitignored — regenerate below)
  main.py                   ← CLI entry point
  generate_report.py        ← Generates PDF analysis report from run data
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

# See all options
python main.py --help
```

---

## Strategies

### Action Strategies

| Strategy          | Description                                                          | House Edge (1M hands) |
| ----------------- | -------------------------------------------------------------------- | --------------------- |
| **Basic**         | Mathematically optimal — lookup table from combinatorial analysis    | 0.76%                 |
| **Counting**      | Basic strategy + index plays adjusted by true count (Illustrious 18) | Context-dependent     |
| **Semi-Random**   | Stand on hard 17+, hit if bust impossible, random otherwise          | 6.03%                 |
| **Dealer Mirror** | Copies dealer rules exactly — never doubles or splits                | 6.04%                 |
| **Random**        | Random legal action — pure baseline                                  | 42.36%                |

### Betting Strategies

| Strategy            | Description                             | Avg Net / 1000 hands | Bust Rate |
| ------------------- | --------------------------------------- | -------------------- | --------- |
| **Flat**            | Fixed bet every hand — baseline         | -$69                 | 0.6%      |
| **Martingale**      | Double after loss, reset after win      | -$91                 | 40.9%     |
| **Anti-Martingale** | Double after win, reset after loss      | -$108                | 36.7%     |
| **Count-Based**     | Scale bet with true count (1-8x spread) | Varies               | Varies    |

_Session results: 10,000 sessions × 1,000 hands, $1,000 starting bankroll,
$10 base bet, Vegas Strip rules, seed 42._

---

## Key Findings

### Hand Analysis (strategy_comparison.ipynb)

**Basic strategy reduces house edge from 42.4% to 0.76%** — a 41.6 percentage
point improvement over random play. This comes from specific, identifiable
decision points: doubling on 9-11 vs weak dealer, standing on 12-16 vs dealer
2-6, and splitting pairs correctly.

**The most counterintuitive finding:** Semi-Random has the lowest bust rate
(12.3%) of all four strategies — lower even than Basic (15.9%) — yet its house
edge is 8x worse. Randomly standing on 12-16 avoids busts but trades them for
standing losses. Basic strategy accepts calculated bust risk because the
alternative is worse. Avoiding busts is not the goal. Maximizing expected
value is.

### Session Analysis (session_analysis.ipynb)

**Betting systems do not change expected value — they change variance.**
Martingale produces a 40.9% bust rate vs flat betting's 0.6%, with a worse
average net profit. The casino's mathematical edge is unchanged regardless
of bet sizing pattern.

**Bet variation without information is worthless.** Count-based betting with
no counting system produces identical results to flat betting. The information
is the edge — not the betting pattern.

**Card counting works — but conditions matter enormously:**

| Configuration                                              | Avg Net / 1000 hands |
| ---------------------------------------------------------- | -------------------- |
| Basic + Flat (baseline)                                    | -$69                 |
| Basic + Count Betting + HiLo (6 deck)                      | -$21                 |
| Counting Strategy + Count Betting + HiLo (6 deck)          | -$8                  |
| Basic + Count Betting + HiLo (single deck)                 | -$7                  |
| **Counting Strategy + Count Betting + HiLo (single deck)** | **+$34**             |

Single deck with full index plays is the only configuration that produces
a genuine player edge. Modern casinos use 6-8 decks specifically to reduce
counting effectiveness.

**ROI percentages are misleading when bet sizes vary.** A flat bettor wagers
$10,000 over 1,000 hands. A count-based bettor may wager $15,000-$20,000.
All comparisons use net profit in dollars, not ROI.

---

## Casino Configurations

| Config    | Decks | BJ Payout | Dealer Soft 17 | Notes                        |
| --------- | ----- | --------- | -------------- | ---------------------------- |
| `vegas`   | 6     | 3:2       | Hits           | Standard Las Vegas Strip     |
| `single`  | 1     | 3:2       | Stands         | Best conditions for counting |
| `liberal` | 2     | 3:2       | Stands         | Most player-friendly         |
| `tough`   | 6     | 6:5       | Hits           | Worst player conditions      |

---

## Regenerating Analysis Data

The `data/runs/` folder is gitignored. To regenerate:

### Hand Analysis (strategy_comparison.ipynb)

```bash
python main.py --mode hands --strategy basic --config vegas --hands 1000000 --seed 42
python main.py --mode hands --strategy semi_random --config vegas --hands 1000000 --seed 42
python main.py --mode hands --strategy dealer_mirror --config vegas --hands 1000000 --seed 42
python main.py --mode hands --strategy random --config vegas --hands 1000000 --seed 42
```

### Session Analysis (session_analysis.ipynb)

```bash
python main.py --mode sessions --strategy basic --betting flat --config vegas --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy basic --betting martingale --config vegas --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy basic --betting anti --config vegas --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy basic --betting count --config vegas --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy basic --betting count --counting hilo --config vegas --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy basic --betting count --counting hilo --config single --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy random --betting flat --config vegas --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy counting --betting count --counting hilo --config vegas --hands 1000 --sessions 10000 --seed 42
python main.py --mode sessions --strategy counting --betting count --counting hilo --config single --hands 1000 --sessions 10000 --seed 42
```

After regenerating session runs, update the run IDs in `session_analysis.ipynb`
Cell 2. A known improvement — storing the counting system name in `run_metadata.json`
for automatic detection — is tracked in `ARCHITECTURE.md`.

---

## How It Could Be Improved

**Simulator:**

- Store counting system name in `run_metadata.json` — enables automatic run detection
- Full pair splitting with split counter (currently simplified)
- Insurance bet support
- Multi-hand play (multiple players at the table)

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
