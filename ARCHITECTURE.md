# Blackjack Simulator — Architecture

## Overview

Two-layer simulation system with pluggable strategies and configurable environments.

- **Hand Simulator**: simulates individual hands, produces per-decision data
- **Session Simulator**: simulates full playing sessions with bankroll tracking, uses Hand Simulator internally

## Data Flow

CLI (main.py)
→ experiment_runner.py
→ session_simulator.py OR hand_simulator.py directly
→ hand_simulator.py
→ strategy.decide(GameState) → action
→ betting_strategy.bet(GameState, bankroll) → bet size
→ decisions.csv (one row per decision)
→ sessions.csv (one row per session)

## Files

### `simulator/config.py`

- **Class**: `SimulatorConfig` (dataclass)
- **Purpose**: all casino rule settings, no logic
- **Presets**: `vegas_strip()`, `single_deck()`, `liberal_rules()`, `tough_rules()`
- **Key fields**: `num_decks`, `penetration`, `dealer_hits_soft_17`, `blackjack_payout`, `double_allowed`, `card_counting_allowed`
- **Depended on by**: everything

## Decisions Log

- `double_allowed` uses `Literal` type — restricted to "any", "9-11", "10-11"
- Defaults are real Las Vegas Strip rules
- Preset functions hide complexity from `main.py` and CLI

### `simulator/card.py`

- **Classes**: `Suit` (enum), `Rank` (enum), `Card` (frozen dataclass), `Deck`
- **Purpose**: card and deck management, delegates counting to CountingSystem
- **Key methods**: `Deck.deal()`, `Deck.needs_shuffle()`, `Deck.penetration()`, `Deck.running_count`, `Deck.true_count`
- **Depends on**: `counting.py`
- **Depended on by**: `hand.py`, `hand_simulator.py`

### `simulator/counting.py`

- **Classes**: `CountingSystem` (ABC), `NoCount`, `HiLoCount`, `KOCount`, `OmegaIICount`
- **Purpose**: pluggable card counting systems, decoupled from Deck
- **Depends on**: `card.py` (type hints only)
- **Depended on by**: `card.py`, `hand_simulator.py`

## Decisions Log

- Counting systems are pluggable — new systems require no changes to Deck
- `NoCount` is the null object pattern — safe default, no if/None checks needed
- `true_count` lives in Deck not CountingSystem — needs deck size to calculate
- `TYPE_CHECKING` import avoids circular imports between card.py and counting.py

### `simulator/hand.py`

- **Class**: `Hand` (dataclass)
- **Purpose**: holds cards, calculates value, tracks hand state
- **Key methods**: `value()`, `is_soft()`, `is_bust()`, `is_blackjack()`, `can_split()`
- **Key fields**: `is_split_hand`, `is_doubled`
- **Depends on**: `card.py`
- **Depended on by**: `hand_simulator.py`

## Decisions Log

- Ace adjustment lives in Hand.value() — Card always returns 11 for ace
- is_soft() recalculates independently from value() — pure, no shared state
- can_split() uses card value not rank — Ten/King can split
- is_blackjack() requires exactly 2 cards — multi-hit 21 is not blackjack

### `simulator/game_state.py`

- **Type alias**: `Action = Literal["hit", "stand", "double", "split", "surrender"]`
- **Class**: `GameState` (frozen dataclass)
- **Purpose**: immutable snapshot of game at a decision point — the strategy contract
- **Key method**: `legal_actions()` — returns list of currently legal actions
- **Depends on**: nothing
- **Depended on by**: `hand_simulator.py`, all strategies

## Decisions Log

- GameState is frozen — strategy can read but never modify simulator state
- Strategy sees dealer upcard only, never hole card
- Counting fields default to 0 — safe when card_counting_allowed=False
- Action is a Literal type alias — type checker catches invalid action strings
- legal_actions() lets strategies iterate options without checking booleans

### `strategies/base.py`

- **Classes**: `Strategy` (ABC), `BettingStrategy` (ABC)
- **Purpose**: defines the contract all strategies must implement
- **Key methods**: `Strategy.decide(state) -> Action`, `BettingStrategy.bet(state, bankroll) -> float`
- **Default methods**: `name()` returns class name — used in CSV recording
- **Depends on**: `game_state.py`
- **Depended on by**: all strategy implementations

## Decisions Log

- ABC enforces interface — missing decide() or bet() raises TypeError at instantiation
- name() has default implementation — class name, can be overridden
- BettingStrategy doesn't enforce min/max — simulator clamps to config limits

### `strategies/random_strategy.py`

- **Classes**: `RandomStrategy`, `RandomBetting`
- **Purpose**: pure random baseline for comparison
- **Depends on**: `base.py`, `game_state.py`
- **Depended on by**: `experiment_runner.py`, `main.py`

## Decisions Log

- Uses dedicated random.Random instance per strategy — reproducible, independent streams
- RandomStrategy uses state.legal_actions() — never hardcodes action names
- RandomBetting bets 1-10% of bankroll — scales naturally, avoids early bust

### `strategies/basic_strategy.py`

- **Class**: `BasicStrategy`
- **Purpose**: mathematically optimal play via lookup tables
- **Tables**: `_HARD`, `_SOFT`, `_PAIRS` — indexed by (player_value, dealer_upcard)
- **Decision priority**: pairs → soft hands → hard hands
- **Fallback**: double not available → hit, surrender not available → hit
- **Depends on**: `base.py`, `game_state.py`
- **Depended on by**: `experiment_runner.py`, `main.py`

## Decisions Log

- Three separate tables for hard, soft, pairs — matches standard BS notation
- Soft key = value - 11 (non-ace card value)
- \_resolve() handles unavailable actions cleanly — no scattered if/else
- Action codes H/S/D/P/R match published strategy cards — easy to verify

### `strategies/betting_strategies.py`

- **Classes**: `FlatBetting`, `MartingaleBetting`, `AntiMartingaleBetting`, `CountBasedBetting`
- **Purpose**: pluggable betting strategies for session simulator
- **Stateful strategies**: `MartingaleBetting`, `AntiMartingaleBetting` — have update() and reset()
- **Stateless strategies**: `FlatBetting`, `CountBasedBetting` — no state needed
- **Depends on**: `base.py`, `game_state.py`
- **Depended on by**: `session_simulator.py`, `main.py`

## Decisions Log

- update() and reset() are optional conventions — only stateful strategies need them
- CountBasedBetting uses true_count not running_count — normalized for deck size
- AntiMartingale has max_progression cap — prevents astronomically large bets
- Martingale docstring explicitly notes the failure mode — honest documentation

### `simulator/hand_simulator.py`

- **Classes**: `DecisionRecord` (dataclass), `HandResult` (dataclass), `HandSimulator`
- **Purpose**: orchestrates a single hand, records per-decision data
- **Key method**: `play_hand()` → `HandResult`
- **Split handling**: player_hands list — multiple hands processed in loop
- **Depends on**: `card.py`, `hand.py`, `config.py`, `game_state.py`, `strategies/base.py`
- **Depended on by**: `session_simulator.py`, `main.py` (direct hand mode)

## Decisions Log

- DecisionRecord outcome fields start empty — filled by \_resolve_hand() after hand completes
- Split creates new Hand objects — original hand discarded
- \_build_state() zeros counting fields if card_counting_allowed=False
- \_resolve_hand() is the single place outcomes get written — no duplication
- Surrender returns immediately — no dealer play needed
- Dealer logic reads directly from config — no abstraction needed here

### `simulator/session_simulator.py`

- **Classes**: `SessionRecord` (dataclass), `SessionSimulator`
- **Purpose**: full session orchestration with bankroll tracking
- **Key method**: `run_session(num_hands, starting_bankroll)` → `(SessionRecord, list[DecisionRecord])`
- **Depends on**: `card.py`, `config.py`, `counting.py`, `hand_simulator.py`, `strategies/base.py`
- **Depended on by**: `experiment_runner.py`, `main.py`

## Decisions Log

- hasattr checks for reset()/update() — stateless betting strategies need no empty methods
- Bet clamped three ways — config min, config max, available bankroll
- session_id uses uuid4 — unique across parallel runs
- \_build_pre_hand_state() zeroes player fields — honest, cards not yet dealt
- config_id filled by session simulator not hand simulator — owns the config context

### `experiments/experiment_runner.py`

- **Classes**: `ExperimentConfig` (dataclass), `ExperimentRunner`
- **Purpose**: runs multiple experiments, saves results to data/runs/{run_id}/
- **Key method**: `run(mode, num_hands, num_sessions)` → run_id string
- **Output**: decisions.csv, sessions.csv, run_metadata.json
- **Depends on**: all simulator files, all strategy files
- **Depended on by**: `main.py`

## Decisions Log

- add_experiment() + run() pattern — clean separation of setup and execution
- asdict() converts dataclasses to dicts — no manual field mapping
- config_id = experiment name — filters experiments in analysis notebooks
- Progress printing every 100 sessions — long runs feel alive
- run_id is timestamp-based — chronological sorting, human readable

### `main.py`

- **Purpose**: CLI entry point, wires everything together
- **Key flags**: --mode, --strategy, --betting, --config, --counting, --compare
- **Registries**: CONFIGS, STRATEGIES, BETTING, COUNTING — add one line to extend
- **Depends on**: all experiment and strategy files
- **Depended on by**: nothing — top of the dependency tree

## Decisions Log

- Registry pattern — adding new strategy = one line, no other changes
- --compare flag runs full matrix in one command
- sys.path.insert ensures imports work from any directory
- RawDescriptionHelpFormatter preserves example formatting in --help

## Known Bugs

### `Hand.is_soft()` — double-ace misclassification (fixed)

`is_soft()` contained a logic error where the `flipped` variable was
algebraically cancelled out, making the check equivalent to `aces > 0`
before the while loop adjustment. This misclassified A+A as hard 12
instead of soft 12.

### `BasicStrategy.decide()` — A+A pair lookup wrong key (fixed)

`pair_value = value // 2` derived the pair card value from the hand total.
For A+A, `value() == 12`, so `pair_value = 6` — looking up pair-of-6s
instead of pair-of-aces (key 11) in `_PAIRS`. Against dealer 7-11, this
returned hit instead of split.

Both bugs were caught by the unit test suite added in the same session.
Fix: `is_soft()` now returns `aces > 0` after the while loop. Pair lookup
now uses `11 if state.player_is_soft else value // 2`.

### Phase 2→3 boundary audit (all fixed, with regression tests)

A full correctness pass before generating Phase 3 training data surfaced several
issues. Data was regenerated after the fixes (see "Regenerating Analysis Data"
in the README).

- **Split hands scored only the first hand.** `play_hand()` resolved only
  `final_hands[0]`: the second split hand's win/loss never reached the bankroll,
  every decision record in the hand was stamped with the first hand's outcome,
  and a *busted* split hand was dropped entirely (a silent loss leak). Fixed by
  resolving each played-out hand independently, summing payouts for the bankroll
  delta, and stamping each sub-hand's records with its own outcome — the `split`
  decision itself carries the net of both (Option A). `SubResult`/`sub_results`
  was added to expose per-sub-hand detail.

- **Split aces could be hit and resplit.** Real rule: a split ace gets exactly
  one card. Basic strategy was hitting/doubling them — worth ~0.28% of phantom
  player edge, large enough that the house-edge self-check only landed in band
  once fixed. Split aces now take one card and cannot resplit (`Hand.from_split_aces`).

- **`max_splits` did nothing.** `_can_split()` always returned `True`. Now
  enforced via a per-hand split counter.

- **No-peek mutual blackjack mispaid.** With `dealer_peeks=False`, a player
  blackjack paid 3:2 without checking the dealer; a mutual blackjack must push.
  Fixed (the default `dealer_peeks=True` was unaffected).

- **Strategy chart / rules mismatch.** The basic-strategy chart was the S17
  chart while the default config was H17. Resolved by making S17 the default (so
  the chart and the "optimal" reference agree), correcting the S17 surrender
  cells, and adding the soft-double "Ds" fallback (soft 18+ stands when it
  cannot double, instead of hitting).

- **Single-deck shuffled every round.** `single_deck` reshuffled after every
  hand, so the count reset each hand and counting measured only index plays — the
  count-based bet never ramped (bet-above-min fired 0% of the time). Now deals to
  50% penetration so the count builds across hands.

- **Omega II counted the ace as −2.** Canonical Omega II counts the ace as 0
  (tracked separately). Fixed. (Hi-Lo and KO were already correct.)

### Recorded data: legal-action flags

`DecisionRecord` now also stores `can_double` / `can_split` / `can_surrender` at
each decision, so the action space is fully reconstructable from `decisions.csv`
for the Phase 3 model.

### Known simplifications (intentional, not bugs)

- Surrender resolves the whole dealt hand immediately; it is only legal on the
  opening two cards (and `surrender_allowed` defaults off), so it cannot co-occur
  with a split in practice. Left as-is.
- The dealer still plays out even when the player has already busted. Outcomes are
  unaffected (a bust loses regardless), but it draws extra cards that slightly
  perturb the running count in counting runs.
