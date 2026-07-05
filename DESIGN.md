# DESIGN — Blackjack Monte Carlo Simulator

What was built and why — the decisions and their reasoning, kept as a clean snapshot of the
design as it stands. Edited in place, not appended to; the findings live in the
[analysis report](blackjack_analysis_report.pdf), and the correctness history lives in
[ARCHITECTURE.md](ARCHITECTURE.md) under *the correctness audit*. The front door →
[README.md](README.md).

*Snapshot of the completed project · last updated 2026-07-05.*

---

## Objective

Most portfolio analysis happens on pre-existing datasets. This project inverts that: **build
the data source first, then analyze it.** Blackjack is the deliberately chosen domain because
it is *self-validating* — house edge, optimal strategy, and dealer behavior all have published
ground truth, so the simulator's correctness is measurable rather than assumed.

The study then asks three questions of the data:

1. **What does optimal play actually buy?** (Basic strategy vs naive baselines, per-decision.)
2. **What does bet sizing change?** (Betting systems on a fixed edge: EV vs variance vs ruin.)
3. **When does counting pay?** (Count-driven play and betting, across deck counts and rules.)

A fourth purpose was designed in from the start and paid off later: the per-decision records
and the pluggable strategy seam were built so that a *future learned agent* could plug into the
same engine and be graded on the same terms. That future arrived as
[blackjack-rl](https://github.com/arda-basarici/blackjack-rl), which consumes this engine
read-only.

---

## The decisions

**Two simulators, layered — hands inside sessions.** Per-hand play and session-level betting
are different questions with different units of analysis, so they are different simulators: the
hand simulator produces one record per *decision* (pure strategy comparison — no bankroll), and
the session simulator drives it hand-by-hand to produce one record per *session* (bankroll,
bet sizing, ruin). Each analysis reads the grain it needs; neither question contaminates the
other.

**A frozen `GameState` is the strategy boundary.** At every decision the strategy receives an
immutable snapshot exposing exactly what a real player may see — hand value, softness, dealer
*upcard* (never the hole card), legal actions, and the count only when the rules allow counting.
Strategies can read but never touch simulator state, and information honesty is enforced by
construction rather than by discipline. `legal_actions()` lives on the state so a strategy
iterates options instead of re-deriving rule booleans.

**Everything a player chooses is pluggable behind two small contracts.** `Strategy.decide(state)
→ action` and `BettingStrategy.bet(state, bankroll) → wager` are the only seams the engine
knows; counting systems are likewise pluggable behind `CountingSystem`, with `NoCount` as the
null object so "no counting" needs no special cases. Adding a player — rule set, counting
variant, or (later) a trained model — is one class and one registry line, no engine changes.
This is the decision the successor project leaned on hardest.

**Casino rules are data, not code.** A frozen config carries decks, penetration, payout, dealer
soft-17 behavior, double/split/surrender permissions — with presets that are real rule-sets
(`vegas`, `single`, `liberal`, `tough`). Controlled experiments change one field and measure
the effect. Two alignment choices matter and are deliberate: the default is **S17 so that the
basic-strategy chart and the rules it was derived for agree** (an H17 default silently
mismatched the chart until the audit caught it), and the counting runs pin 6-deck and
single-deck to the **same penetration (0.5)** so the deck-count comparison isolates deck count
alone.

**Records are built for reuse, not just for the study.** Every decision row carries the full
context — state, action, outcome, payout, count — *plus the legal-action flags* (`can_double`,
`can_split`, `can_surrender`), so the action space is reconstructable from the data alone.
That last field exists purely for the successor learner; it cost one line and made the dataset
model-ready.

**Runs are reproducible by construction.** One seed (42), and every analysis run has a stable,
self-describing name (`hands_basic`, `sess_counting_hilo_1d`, …) written by one command
(`regenerate_data.py`, 13 runs, ~90M hands). The notebooks and the report reference names, not
timestamps, so regeneration never invalidates them. Data is git-ignored and regenerable; the
committed artifacts are the code, the seed, and the report.

**The comparison metric is edge per dollar wagered, in net dollars.** Counting strategies raise
bets at favorable counts and so wager 2–2.4× more than a flat bettor; a return-on-bankroll
figure flatters them structurally. Net dollars per 1,000 hands beside ruin rate — never
collapsed into one number — is the honest comparison, and the report states it as such.

---

## Outcome

Basic strategy's measured 0.45% house edge validates the engine against published numbers, and
the study's findings follow: optimal play is worth ~45 points of edge over random; low bust
rate is not low house edge (the Semi-Random paradox); betting systems move variance and ruin,
never EV; count-*shaped* betting without count *information* is flat betting; and only
single-deck counting with index plays yields a genuine player edge (+$314 / 1,000 hands) — 
paired with the highest ruin risk of any positive configuration (20.4%). EV and survival are
independent levers. Full analysis: [blackjack_analysis_report.pdf](blackjack_analysis_report.pdf).

---

## Scope & non-goals

- **No claim beyond the simulated family.** One player seat, no insurance, surrender only on
  the opening two cards, dealer plays a fixed rule. Intentional simplifications are catalogued
  in [ARCHITECTURE.md](ARCHITECTURE.md).
- **No uncertainty quantification.** Findings ride on large samples (1M–90M hands) as point
  estimates; confidence intervals and sampling-error discipline became a *methodological
  finding of the successor project*, not this one — stated here honestly rather than
  retrofitted.
- **No optimization.** The counting spread (1–8×) was chosen, not tuned; bet-spread and
  penetration optimization were left as future work, and the successor project later derived a
  spread from a measured edge curve instead.

## Future work (curated)

Considered and consciously not done here: insurance and multi-seat play; composition-dependent
basic strategy; Wonging (sitting out bad counts); KO-vs-Hi-Lo comparison (both systems are
implemented; the comparison was never run); rule-variation pricing (6:5 vs 3:2 quantified);
bankroll-vs-ruin mapping. Several of these threads — Wonging, bankroll sweeps, spread
derivation — were in fact picked up and answered in
[blackjack-rl](https://github.com/arda-basarici/blackjack-rl)'s betting study.

---

## The successor contract

blackjack-rl consumes this engine as an installed package (`simulator`, `strategies`,
`experiments` — packaging metadata was the only change ever made for it) under one promise:
**the engine is never modified.** Its validated 0.45% anchor and the `Strategy` contract are
the ground truth that project grades against; every learned policy is wrapped as a `Strategy`
and played through this engine unchanged.
