from simulator.game_state import GameState, Action
from strategies.base import Strategy


class SemiRandomStrategy(Strategy):
    """
    Stands on hard 17 or higher, hits on soft 17.
    Random action otherwise — hit or stand only, no doubles or splits.
    Represents a naive player who knows one basic rule.
    """

    def __init__(self, seed: int | None = None) -> None:
        import random
        self._rng = random.Random(seed)

    def decide(self, state: GameState) -> Action:
        # Can't bust — always hit
        # Hard: value <= 11 (max card = 11, 11+11=22 but ace adjusts)
        # Soft: value <= 16 (ace absorbs any card)
        if state.player_value <= 11:
            return "hit"
        if state.player_is_soft and state.player_value <= 16:
            return "hit"

        # Hard 17+ — always stand
        if state.player_value >= 17 and not state.player_is_soft:
            return "stand"

        # Soft 17 — hit
        if state.player_is_soft and state.player_value == 17:
            return "hit"

        # Soft 18+ — stand
        if state.player_is_soft and state.player_value >= 18:
            return "stand"

        # Hard 12-16 — random
        return self._rng.choice(["hit", "stand"])

    def name(self) -> str:
        return "semi_random"


class DealerMirrorStrategy(Strategy):
    """
    Copies dealer rules exactly:
    - Hit until hard 17 or higher
    - Hit soft 17 (if dealer_hits_soft_17 would apply)
    - Never double, never split, never surrender
    
    Common strategy people try — performs worse than basic
    because it never exploits doubling or splitting opportunities.
    Interesting because dealer uses same rules yet has house edge —
    this demonstrates why position (acting first) matters.
    """

    def decide(self, state: GameState) -> Action:
        # Hit on soft 17 or below 17
        if state.player_value < 17:
            return "hit"
        if state.player_value == 17 and state.player_is_soft:
            return "hit"
        return "stand"

    def name(self) -> str:
        return "dealer_mirror"