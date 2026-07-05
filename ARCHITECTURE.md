# ARCHITECTURE — Blackjack Monte Carlo Simulator

How the engine is built and why that structure — the module graph, the seams, and the
correctness audit that earned the "validated" label. Kept as a clean snapshot of the code as
it stands, edited in place. What was decided and why → [DESIGN.md](DESIGN.md); the front door
→ [README.md](README.md).

*Snapshot of the completed project · last updated 2026-07-05.*

---

## Design shape

Two contracts split the system into an engine that never knows who is playing and players that
never touch engine state:

```
        strategies/                          the pluggable players
          base.py        Strategy · BettingStrategy   (the two ABCs)
          basic / counting / rule-based / random · betting systems
                 ▲
                 │  decide(GameState) → Action
                 │  bet(GameState, bankroll) → wager      the only boundary
                 ▼
        simulator/                           the engine
          config.py      frozen casino rules (+ the four presets)
          card.py        Card · Deck  ──►  counting.py   CountingSystem
          hand.py        hand value, soft/hard, bust, split rules      (Hi-Lo / KO / Omega II /
          game_state.py  the frozen per-decision snapshot               NoCount — pluggable)
          hand_simulator.py     one hand, per-decision records
          session_simulator.py  hands in a session: shoe, bankroll, ruin
                 │
                 ▼
        experiments/experiment_runner.py     named runs → data/runs/<run-id>/
                 │                           (decisions.csv · sessions.csv · run_metadata.json)
                 ▼
        main.py · regenerate_data.py         CLI / the 13 canonical runs
        analysis/ · generate_report.py       notebooks + the PDF — read data/runs/, never simulate
```

The rules, stated once:

- **The engine imports only the ABCs.** `simulator/` knows `Strategy` and `BettingStrategy`,
  never a concrete player; `strategies/` sees only the frozen `GameState`. Registries in
  `main.py` are where the two sides meet.
- **Information honesty is structural.** `GameState` is immutable, exposes the dealer upcard
  and never the hole card, and zeroes the count fields when the rules forbid counting — a
  strategy cannot cheat even by accident.
- **Effects live at the edges.** Card/hand/state/strategy logic is pure and unit-testable;
  dealing and RNG live in the simulators; file I/O lives in the experiment runner and the
  report/notebook layer.
- **Analysis never simulates.** Notebooks and the report generator read `data/runs/` through
  stable run names; one command (`regenerate_data.py`) rebuilds all 13 runs from seed 42.

### The life of a run

```
  config preset + seed 42
        │
        ▼
  hand / session simulator ──► per-decision + per-session records
        │
        ▼
  data/runs/<stable-name>/     decisions.csv · sessions.csv · run_metadata.json
        │                      (git-ignored — regenerable by construction)
        ▼
  analysis notebooks · generate_report.py ──► blackjack_analysis_report.pdf  (committed)
```

## Module responsibilities

One line per module; detail lives in the docstrings.

| module | single job |
| --- | --- |
| `simulator/config.py` | frozen casino-rule dataclass + the four real-rules presets (`vegas`, `single`, `liberal`, `tough`) |
| `simulator/card.py` | `Card`, `Deck`: dealing, penetration-triggered shuffle, count delegation to the counting system |
| `simulator/counting.py` | `CountingSystem` ABC + Hi-Lo, KO, Omega II, and `NoCount` (the null object) |
| `simulator/hand.py` | hand arithmetic: value with ace adjustment, soft/hard, bust, blackjack, split legality |
| `simulator/game_state.py` | the frozen decision snapshot + `Action` literal type + `legal_actions()` |
| `simulator/hand_simulator.py` | one hand end-to-end: drive the strategy, handle splits, resolve outcomes, emit `DecisionRecord`s |
| `simulator/session_simulator.py` | one session: persistent shoe, bankroll with three-way bet clamping, ruin, emit `SessionRecord` |
| `strategies/base.py` | the two contracts: `Strategy.decide`, `BettingStrategy.bet` (+ optional `update`/`reset` for stateful bettors) |
| `strategies/basic_strategy.py` | the optimal lookup: hard/soft/pair tables in published chart notation, fallbacks for unavailable actions |
| `strategies/rule_based_strategies.py` | Semi-Random, Dealer Mirror, and the counting strategy (basic + Illustrious-18 index plays) |
| `strategies/random_strategy.py` | the random floor: `RandomStrategy` + `RandomBetting` (own RNG stream, draws only from `legal_actions()`) |
| `strategies/betting_strategies.py` | flat, martingale, anti-martingale (capped), count-based spread |
| `experiments/experiment_runner.py` | named experiment batches → `data/runs/` CSVs + metadata, progress reporting |
| `main.py` | CLI: registry pattern (one line to add a strategy / config / counting system), `--compare` matrix |
| `regenerate_data.py` | the 13 canonical runs under stable names — full scale or `--quick` |
| `generate_report.py` | the PDF report from run data (matplotlib/seaborn figures, reportlab layout) |

## Seams that carried weight

- **`GameState` + `Action`** — the whole engine↔player boundary in one frozen dataclass and one
  `Literal` type; the type checker rejects invalid actions at write time.
- **`CountingSystem` behind the deck** — counting is observed, never consulted, by the deck;
  systems swap without touching `Deck`, and `NoCount` keeps the no-counting path branch-free.
- **Stateful betting by convention** — `update(outcome)` / `reset()` exist only on bettors that
  need them (martingale family); the session simulator feature-detects rather than forcing
  empty methods on stateless bettors.
- **Stable run names** — the contract between data generation and every consumer (notebooks,
  report). Regeneration is invisible to downstream code.

---

## The correctness audit

The engine's "validated" status was **earned, not assumed**. Before the successor project was
allowed to consume it as ground truth, a full correctness pass audited the engine against the
published numbers — and found real bugs, each now fixed and pinned by a regression test
(`tests/test_simulator_rules.py`, `tests/test_hand_simulator.py`; 83 tests in all). All
analysis data was regenerated after the fixes. What the audit caught, as classes of failure:

- **Settlement:** split hands scored only the first hand — the second hand's result never
  reached the bankroll, its records carried the wrong outcome, and a busted split hand was a
  silent loss leak. Each sub-hand now resolves independently and stamps its own records; the
  split decision carries the net.
- **Rules:** split aces could be hit and resplit (real rule: one card each — worth ~0.28% of
  phantom player edge, enough to push the measured house edge out of the published band);
  `max_splits` was never enforced; a no-peek mutual blackjack paid 3:2 instead of pushing.
- **Reference alignment:** the default rules were H17 while the basic-strategy chart is the S17
  chart — the "optimal" reference disagreed with the world it played in. S17 became the
  default; the chart's surrender cells and the soft-double fallback were corrected with it.
- **Counting environment:** the single-deck preset reshuffled every hand, so the count reset
  before it could build — count-based betting measurably never ramped; and Omega II counted
  the ace as −2 where the canonical system counts it 0.
- Two earlier unit-test catches in the same spirit: `is_soft()` misclassified A+A as hard 12,
  and the pair-lookup derived pair-of-6s from an A+A total of 12.

The lasting lesson is structural: **the self-validation loop works.** Every one of these was
caught by comparing measured behavior against published ground truth or by a test asserting a
rule the code claimed to implement — the same discipline the successor project then scaled up.

### Known simplifications (intentional, documented, not bugs)

- Surrender resolves the whole dealt hand immediately; legal only on the opening two cards
  (default off), so it cannot co-occur with a split in practice.
- The dealer plays out even when the player has already busted — outcomes are unaffected, but
  the extra cards slightly perturb the running count in counting runs.
- One player seat; no insurance bet.

---

## Deliberately not done

- **No gym-style `reset()/step()` environment.** The successor's RL work captured episodes
  through the unmodified engine instead — the atomic `play_hand()` was sufficient, by design.
- **No plugin/registry framework beyond `main.py`'s dicts.** One line per new strategy carried
  the whole study; a heavier harness never earned its cost.
- **No counting-system field in `run_metadata.json`.** Runs are distinguished by stable name;
  adding the field is trivial if ad-hoc counting runs ever multiply.
- **No parallel execution.** ~90M hands regenerate in acceptable wall-clock single-threaded;
  parallelism arrived (with merged accumulators and per-worker seeds) in the successor project,
  where 20M-hand *per-experiment* measurements demanded it.
