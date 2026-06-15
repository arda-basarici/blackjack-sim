"""
Regenerate every simulator run the analysis notebooks depend on, with STABLE,
self-describing run ids (no timestamps). Re-run this whenever the simulator
changes; each run overwrites its own directory under data/runs/<name>/, so the
notebooks always find the latest data under a fixed name.

    python regenerate_data.py            # full scale (matches the notebooks)
    python regenerate_data.py --quick    # small scale for a fast sanity check

Full scale is ~90M+ simulated hands and takes a while (pure Python). The two
duplicate "basic + count" runs differ by counting system: one with no counter
(true count always 0 -> a flat-bet baseline) and one with Hi-Lo.
"""

import argparse
import time
from dataclasses import replace

from simulator.config import vegas_strip, single_deck
from simulator.counting import HiLoCount, NoCount
from strategies.basic_strategy import BasicStrategy
from strategies.random_strategy import RandomStrategy
from strategies.rule_based_strategies import (
    SemiRandomStrategy,
    DealerMirrorStrategy,
    CardCountingStrategy,
)
from strategies.betting_strategies import (
    FlatBetting,
    MartingaleBetting,
    AntiMartingaleBetting,
    CountBasedBetting,
)
from experiments.experiment_runner import ExperimentRunner, ExperimentConfig

SEED = 42

# Penetration for the card-counting runs. The 6-deck and single-deck counting
# configs are held at the SAME penetration so the 6d-vs-1d comparison isolates
# deck count alone. 0.5 is the deepest a single deck can safely run (guarantees
# >=27 cards at every hand start). Non-counting runs keep the realistic 0.75 —
# penetration is immaterial without a counter, so the count_nocount control
# stays an exact match to flat.
COUNT_PEN = 0.5


def _run(run_id, mode, *, strategy, betting=None, config=None, counting=None,
         num_hands, num_sessions=1):
    runner = ExperimentRunner(run_id=run_id)
    runner.add_experiment(ExperimentConfig(
        name=run_id,
        config=config or vegas_strip(),
        strategy=strategy,
        betting_strategy=betting or FlatBetting(),
        counting_system=counting or NoCount(),
    ))
    runner.run(mode=mode, num_hands=num_hands, num_sessions=num_sessions, seed=SEED)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true",
                    help="small scale for a fast check (not for the final notebooks)")
    args = ap.parse_args()

    H = 100_000 if args.quick else 1_000_000            # hands-mode hand count
    SH, SS = (200, 1_000) if args.quick else (1_000, 10_000)  # sessions: hands, sessions

    t0 = time.time()

    # --- hands mode: per-strategy decision data (feeds eda / strategy_comparison) ---
    _run("hands_basic",         "hands", strategy=BasicStrategy(),             num_hands=H)
    _run("hands_random",        "hands", strategy=RandomStrategy(seed=SEED),   num_hands=H)
    _run("hands_semi_random",   "hands", strategy=SemiRandomStrategy(seed=SEED), num_hands=H)
    _run("hands_dealer_mirror", "hands", strategy=DealerMirrorStrategy(),      num_hands=H)

    # --- sessions mode: bankroll trajectories (feeds eda2 / session_analysis) ---
    _run("sess_basic_flat",          "sessions", strategy=BasicStrategy(), betting=FlatBetting(),
         num_hands=SH, num_sessions=SS)
    _run("sess_basic_martingale",    "sessions", strategy=BasicStrategy(), betting=MartingaleBetting(),
         num_hands=SH, num_sessions=SS)
    _run("sess_basic_anti",          "sessions", strategy=BasicStrategy(), betting=AntiMartingaleBetting(),
         num_hands=SH, num_sessions=SS)
    _run("sess_basic_count_nocount", "sessions", strategy=BasicStrategy(), betting=CountBasedBetting(),
         counting=NoCount(), num_hands=SH, num_sessions=SS)
    _run("sess_basic_count_hilo_6d", "sessions", strategy=BasicStrategy(), betting=CountBasedBetting(),
         counting=HiLoCount(), config=replace(vegas_strip(), penetration=COUNT_PEN), num_hands=SH, num_sessions=SS)
    _run("sess_basic_count_hilo_1d", "sessions", strategy=BasicStrategy(), betting=CountBasedBetting(),
         counting=HiLoCount(), config=replace(single_deck(), penetration=COUNT_PEN), num_hands=SH, num_sessions=SS)
    _run("sess_random_flat",         "sessions", strategy=RandomStrategy(seed=SEED), betting=FlatBetting(),
         num_hands=SH, num_sessions=SS)
    _run("sess_counting_hilo_6d",    "sessions", strategy=CardCountingStrategy(), betting=CountBasedBetting(),
         counting=HiLoCount(), config=replace(vegas_strip(), penetration=COUNT_PEN), num_hands=SH, num_sessions=SS)
    _run("sess_counting_hilo_1d",    "sessions", strategy=CardCountingStrategy(), betting=CountBasedBetting(),
         counting=HiLoCount(), config=replace(single_deck(), penetration=COUNT_PEN), num_hands=SH, num_sessions=SS)

    print(f"\nAll runs regenerated in {time.time() - t0:.0f}s.")


if __name__ == "__main__":
    main()
