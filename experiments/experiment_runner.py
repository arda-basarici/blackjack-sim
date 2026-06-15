import os
import json
import uuid
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, asdict

from simulator.config import SimulatorConfig
from simulator.session_simulator import SessionSimulator, SessionRecord
from simulator.hand_simulator import HandSimulator, DecisionRecord
from simulator.card import Deck
from simulator.counting import CountingSystem
from strategies.base import Strategy, BettingStrategy
from strategies.random_strategy import RandomStrategy, RandomBetting
from strategies.basic_strategy import BasicStrategy
from strategies.betting_strategies import FlatBetting


@dataclass
class ExperimentConfig:
    """
    Defines one experiment — a specific combination of
    simulator config, strategy, and betting strategy.
    """
    name: str
    config: SimulatorConfig
    strategy: Strategy
    betting_strategy: BettingStrategy
    counting_system: CountingSystem | None = None


class ExperimentRunner:
    """
    Runs one or more experiments and saves results to data/runs/{run_id}/.

    Supports two modes:
        - hands mode: runs HandSimulator directly, produces decisions.csv only
        - sessions mode: runs SessionSimulator, produces both CSVs

    Usage:
        runner = ExperimentRunner(output_dir="data/runs")
        runner.add_experiment(ExperimentConfig(...))
        runner.run(mode="sessions", num_hands=100, num_sessions=1000)
    """

    def __init__(self, output_dir: str = "data/runs", run_id: str | None = None) -> None:
        self._output_dir = output_dir
        self._experiments: list[ExperimentConfig] = []
        # A stable, caller-supplied run_id makes runs reproducible and lets the
        # notebooks reference them by a fixed name; otherwise fall back to a
        # timestamp so ad-hoc runs never collide.
        self._run_id = run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def add_experiment(self, experiment: ExperimentConfig) -> None:
        self._experiments.append(experiment)

    def run(
        self,
        mode: str,                  # "hands" or "sessions"
        num_hands: int = 100_000,
        num_sessions: int = 1,
        starting_bankroll: float | None = None,
        seed: int | None = None,
    ) -> str:
        """
        Run all registered experiments.
        Returns run_id for loading results later.
        """
        if not self._experiments:
            raise ValueError("No experiments added. Call add_experiment() first.")

        run_dir = os.path.join(self._output_dir, self._run_id)
        os.makedirs(run_dir, exist_ok=True)

        all_decisions: list[dict] = []
        all_sessions: list[dict] = []

        for experiment in self._experiments:
            config_id = experiment.name
            print(f"Running experiment: {config_id}")

            if mode == "hands":
                decisions = self._run_hands_mode(
                    experiment, config_id, num_hands, seed
                )
                all_decisions.extend(decisions)

            elif mode == "sessions":
                decisions, sessions = self._run_sessions_mode(
                    experiment, config_id,
                    num_hands, num_sessions,
                    starting_bankroll, seed
                )
                all_decisions.extend(decisions)
                all_sessions.extend(sessions)

            else:
                raise ValueError(f"Unknown mode: {mode}. Use 'hands' or 'sessions'.")

        # Save results
        self._save_results(run_dir, all_decisions, all_sessions, mode, num_hands, num_sessions, seed)

        print(f"\nRun complete. Results saved to: {run_dir}")
        return self._run_id

    def _run_hands_mode(
        self,
        experiment: ExperimentConfig,
        config_id: str,
        num_hands: int,
        seed: int | None,
    ) -> list[dict]:
        """Run HandSimulator directly — no bankroll tracking."""
        import random
        if seed is not None:
            random.seed(seed)

        deck = Deck(
            num_decks=experiment.config.num_decks,
            counting_system=experiment.counting_system,
        )
        simulator = HandSimulator(experiment.config, deck, experiment.strategy)

        all_decisions: list[dict] = []

        for i in range(num_hands):
            if deck.needs_shuffle(
                experiment.config.penetration,
                experiment.config.shuffle_every_round
            ):
                deck.build()
            result = simulator.play_hand(
                session_id="direct",
                bankroll=0.0,
                bet_size=experiment.config.min_bet,
                hands_played=i,
            )

            for record in result.decision_records:
                record.config_id = config_id
                all_decisions.append(asdict(record))

        return all_decisions

    def _run_sessions_mode(
        self,
        experiment: ExperimentConfig,
        config_id: str,
        num_hands: int,
        num_sessions: int,
        starting_bankroll: float | None,
        seed: int | None,
    ) -> tuple[list[dict], list[dict]]:
        """Run SessionSimulator — full bankroll tracking."""
        import random
        if seed is not None:
            random.seed(seed)

        all_decisions: list[dict] = []
        all_sessions: list[dict] = []

        for session_num in range(num_sessions):
            if session_num % 100 == 0:
                print(f"  Session {session_num}/{num_sessions}")

            session_sim = SessionSimulator(
                config=experiment.config,
                strategy=experiment.strategy,
                betting_strategy=experiment.betting_strategy,
                counting_system=experiment.counting_system,
                config_id=config_id,
            )

            session_record, decisions = session_sim.run_session(
                num_hands=num_hands,
                starting_bankroll=starting_bankroll,
            )

            all_sessions.append(asdict(session_record))
            all_decisions.extend([asdict(d) for d in decisions])

        return all_decisions, all_sessions

    def _save_results(
        self,
        run_dir: str,
        all_decisions: list[dict],
        all_sessions: list[dict],
        mode: str,
        num_hands: int,
        num_sessions: int,
        seed: int | None,
    ) -> None:
        """Save CSVs and metadata to run directory."""

        # Save decisions
        if all_decisions:
            decisions_df = pd.DataFrame(all_decisions)
            decisions_path = os.path.join(run_dir, "decisions.csv")
            decisions_df.to_csv(decisions_path, index=False)
            print(f"Saved {len(decisions_df)} decision records → decisions.csv")

        # Save sessions
        if all_sessions:
            sessions_df = pd.DataFrame(all_sessions)
            sessions_path = os.path.join(run_dir, "sessions.csv")
            sessions_df.to_csv(sessions_path, index=False)
            print(f"Saved {len(sessions_df)} session records → sessions.csv")

        # Save metadata
        metadata = {
            "run_id": self._run_id,
            "mode": mode,
            "num_hands": num_hands,
            "num_sessions": num_sessions,
            "seed": seed,
            "experiments": [
                {
                    "name": exp.name,
                    "strategy": exp.strategy.name(),
                    "betting_strategy": exp.betting_strategy.name(),
                    "config": {
                        "num_decks": exp.config.num_decks,
                        "blackjack_payout": exp.config.blackjack_payout,
                        "dealer_hits_soft_17": exp.config.dealer_hits_soft_17,
                        "double_allowed": exp.config.double_allowed,
                        "surrender_allowed": exp.config.surrender_allowed,
                    }
                }
                for exp in self._experiments
            ],
            "timestamp": datetime.now().isoformat(),
        }

        metadata_path = os.path.join(run_dir, "run_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Saved metadata → run_metadata.json")