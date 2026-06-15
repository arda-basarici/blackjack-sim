import argparse
import sys
import os


# Make sure imports work from project root
sys.path.insert(0, os.path.dirname(__file__))

from simulator.config import (
    SimulatorConfig,
    vegas_strip,
    single_deck,
    liberal_rules,
    tough_rules,
)
from simulator.counting import HiLoCount, KOCount, OmegaIICount, NoCount
from strategies.random_strategy import RandomStrategy, RandomBetting
from strategies.basic_strategy import BasicStrategy
from strategies.rule_based_strategies import SemiRandomStrategy, DealerMirrorStrategy, CardCountingStrategy
from strategies.betting_strategies import (
    FlatBetting,
    MartingaleBetting,
    AntiMartingaleBetting,
    CountBasedBetting,
)
from experiments.experiment_runner import ExperimentRunner, ExperimentConfig
from typing import Type
from strategies.base import Strategy, BettingStrategy
from simulator.counting import CountingSystem

# --- Registry of available options ---

CONFIGS: dict[str, SimulatorConfig] = {
    "vegas":    vegas_strip(),
    "single":   single_deck(),
    "liberal":  liberal_rules(),
    "tough":    tough_rules(),
}

STRATEGIES: dict[str, Type[Strategy]] = {
    "random":   RandomStrategy,
    "basic":    BasicStrategy,
    "semi_random":   SemiRandomStrategy,
    "dealer_mirror": DealerMirrorStrategy,
    "counting":      CardCountingStrategy,
}

BETTING: dict[str, Type[BettingStrategy]] = {
    "flat":         FlatBetting,
    "martingale":   MartingaleBetting,
    "anti":         AntiMartingaleBetting,
    "count":        CountBasedBetting,
    "random_bet":       RandomBetting,
}

COUNTING: dict[str, Type[CountingSystem]] = {
    "hilo":     HiLoCount,
    "ko":       KOCount,
    "omega":    OmegaIICount,
    "none":     NoCount,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Blackjack Monte Carlo Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run 100k hands with basic strategy, vegas rules
  python main.py --mode hands --strategy basic --config vegas --hands 100000

  # Run 1000 sessions with basic strategy and flat betting
  python main.py --mode sessions --strategy basic --betting flat --config vegas --hands 100 --sessions 1000

  # Compare all strategies on vegas rules
  python main.py --mode sessions --compare --config vegas --hands 100 --sessions 500

  # Run with card counting
  python main.py --mode hands --strategy basic --counting hilo --config vegas --hands 100000
        """
    )

    parser.add_argument(
        "--mode",
        choices=["hands", "sessions"],
        required=True,
        help="hands: hand-level data only | sessions: full bankroll tracking"
    )

    parser.add_argument(
        "--strategy",
        choices=list(STRATEGIES.keys()),
        default="basic",
        help="Action strategy (default: basic)"
    )

    parser.add_argument(
        "--betting",
        choices=list(BETTING.keys()),
        default="flat",
        help="Betting strategy (default: flat)"
    )

    parser.add_argument(
        "--config",
        choices=list(CONFIGS.keys()),
        default="vegas",
        help="Casino rule config (default: vegas)"
    )

    parser.add_argument(
        "--counting",
        choices=list(COUNTING.keys()),
        default="none",
        help="Card counting system (default: none)"
    )

    parser.add_argument(
        "--hands",
        type=int,
        default=100_000,
        help="Number of hands per session (default: 100000)"
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=1,
        help="Number of sessions — sessions mode only (default: 1)"
    )

    parser.add_argument(
        "--bankroll",
        type=float,
        default=None,
        help="Starting bankroll — sessions mode only (default: from config)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run all strategy combinations and compare results"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="data/runs",
        help="Output directory for results (default: data/runs)"
    )

    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Stable run directory name (default: timestamped run_YYYYMMDD_HHMMSS)"
    )

    return parser


def run_single(args: argparse.Namespace) -> str:
    """Run a single strategy/config combination."""
    config = CONFIGS[args.config]
    strategy = STRATEGIES[args.strategy]()
    betting = BETTING[args.betting]()
    counting = COUNTING[args.counting]()

    experiment_name = f"{args.strategy}_{args.betting}_{args.config}"

    runner = ExperimentRunner(output_dir=args.output, run_id=args.run_id)
    runner.add_experiment(ExperimentConfig(
        name=experiment_name,
        config=config,
        strategy=strategy,
        betting_strategy=betting,
        counting_system=counting,
    ))

    return runner.run(
        mode=args.mode,
        num_hands=args.hands,
        num_sessions=args.sessions,
        starting_bankroll=args.bankroll,
        seed=args.seed,
    )


def run_comparison(args: argparse.Namespace) -> str:
    """Run all strategy combinations for comparison."""
    config = CONFIGS[args.config]
    runner = ExperimentRunner(output_dir=args.output, run_id=args.run_id)

    # Standard comparison matrix
    combinations = [
        ("random", "random_bet"),
        ("random", "flat"),
        ("basic",  "flat"),
        ("basic",  "martingale"),
        ("basic",  "anti"),
        ("basic",  "count"),
    ]

    for strategy_name, betting_name in combinations:
        strategy = STRATEGIES[strategy_name]()
        betting = BETTING[betting_name]()
        counting = COUNTING[args.counting]()
        name = f"{strategy_name}_{betting_name}_{args.config}"

        runner.add_experiment(ExperimentConfig(
            name=name,
            config=config,
            strategy=strategy,
            betting_strategy=betting,
            counting_system=counting,
        ))
        print(f"Added experiment: {name}")

    return runner.run(
        mode=args.mode,
        num_hands=args.hands,
        num_sessions=args.sessions,
        starting_bankroll=args.bankroll,
        seed=args.seed,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(f"Blackjack Simulator")
    print(f"Mode:     {args.mode}")
    print(f"Config:   {args.config}")
    print(f"Strategy: {args.strategy}")
    print(f"Hands:    {args.hands:,}")
    if args.mode == "sessions":
        print(f"Sessions: {args.sessions:,}")
    print()

    if args.compare:
        run_id = run_comparison(args)
    else:
        run_id = run_single(args)

    print(f"\nRun ID: {run_id}")
    print(f"Load results with:")
    print(f"  pd.read_csv('data/runs/{run_id}/decisions.csv')")
    if args.mode == "sessions":
        print(f"  pd.read_csv('data/runs/{run_id}/sessions.csv')")


if __name__ == "__main__":
    main()