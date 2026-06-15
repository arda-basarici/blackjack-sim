from simulator.game_state import GameState, Action
from strategies.base import Strategy
from strategies.basic_strategy import BasicStrategy


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
        

class CardCountingStrategy(Strategy):
    """
    Basic Strategy with index play deviations based on true count.
    Implements a subset (~12) of the most impactful count-based
    adjustments — drawn from the 'Illustrious 18', the deviations
    that account for most of the gain from learning index plays.
    (Insurance and a few of the 18, e.g. 12 vs 4/5/6, are not yet included.)

    Uses BasicStrategy as the foundation and overrides specific
    decisions when the true count crosses key thresholds.

    Only meaningful when paired with a counting system (e.g. HiLo)
    and card_counting_allowed=True in config. Without a counting
    system, true_count=0 always and this behaves identically to
    BasicStrategy.
    """

    def __init__(self) -> None:
        self._basic = BasicStrategy()

    def decide(self, state: GameState) -> Action:
        tc = state.true_count
        pv = state.player_value
        du = state.dealer_upcard
        soft = state.player_is_soft

        # --- Index plays (Illustrious 18) ---
        # Each deviation is: (condition) -> override action
        # Only applied when the action is actually legal

        # Insurance — take at TC +3 or higher
        # (handled externally as a side bet — skip for now)

        # 16 vs 10: stand at TC 0 or higher (normally hit)
        if pv == 16 and du == 10 and not soft:
            if tc >= 0:
                return "stand"

        # 15 vs 10: stand at TC +4 or higher (normally hit)
        if pv == 15 and du == 10 and not soft:
            if tc >= 4:
                return "stand"

        # 12 vs 3: stand at TC +2 or higher (normally hit)
        if pv == 12 and du == 3 and not soft:
            if tc >= 2:
                return "stand"

        # 12 vs 2: stand at TC +3 or higher (normally hit)
        if pv == 12 and du == 2 and not soft:
            if tc >= 3:
                return "stand"

        # 11 vs Ace: double at TC +1 or higher (normally hit)
        if pv == 11 and du == 11 and not soft:
            if tc >= 1 and state.can_double:
                return "double"

        # 10 vs 10: double at TC +4 or higher (normally hit)
        if pv == 10 and du == 10 and not soft:
            if tc >= 4 and state.can_double:
                return "double"

        # 10 vs Ace: double at TC +3 or higher (normally hit)
        if pv == 10 and du == 11 and not soft:
            if tc >= 3 and state.can_double:
                return "double"

        # 9 vs 2: double at TC +1 or higher (normally hit)
        if pv == 9 and du == 2 and not soft:
            if tc >= 1 and state.can_double:
                return "double"

        # 9 vs 7: double at TC +3 or higher (normally hit)
        if pv == 9 and du == 7 and not soft:
            if tc >= 3 and state.can_double:
                return "double"

        # 16 vs 9: stand at TC +5 or higher (normally hit)
        if pv == 16 and du == 9 and not soft:
            if tc >= 5:
                return "stand"

        # 13 vs 2: stand at TC -1 or higher (basic already stands,
        # but at very negative counts should hit — deviation is to hit)
        if pv == 13 and du == 2 and not soft:
            if tc <= -1:
                return "hit"

        # 13 vs 3: stand at TC -2 or higher
        if pv == 13 and du == 3 and not soft:
            if tc <= -2:
                return "hit"

        # Fall back to basic strategy for everything else
        return self._basic.decide(state)

    def name(self) -> str:
        return "counting_strategy"