"""The random floor: uniformly random play and betting, the baseline under every claim.

``RandomStrategy`` draws only from ``state.legal_actions()`` (never hardcodes action
names); ``RandomBetting`` bets a random fraction of bankroll. Each carries its own seeded
``random.Random`` instance so streams are reproducible and independent of the deck's RNG.
"""

import random
from simulator.game_state import GameState, Action
from strategies.base import Strategy, BettingStrategy


class RandomStrategy(Strategy):
    """
    Picks a random legal action at every decision point.
    
    Used as a baseline — any reasonable strategy should
    significantly outperform random play.
    Also useful for stress-testing the simulator since it
    exercises all possible action paths.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def decide(self, state: GameState) -> Action:
        return self._rng.choice(state.legal_actions())

    def name(self) -> str:
        return "random"


class RandomBetting(BettingStrategy):
    """
    Bets a random amount between min and max bet each hand.
    Paired with RandomStrategy as a pure baseline.
    Simulator clamps to config min_bet/max_bet.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def bet(self, state: GameState, bankroll: float) -> float:
        # Bet between 1% and 10% of current bankroll
        min_bet = bankroll * 0.01
        max_bet = bankroll * 0.10
        return round(self._rng.uniform(min_bet, max_bet), 2)

    def name(self) -> str:
        return "random_betting"