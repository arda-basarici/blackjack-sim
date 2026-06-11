from dataclasses import dataclass
from typing import Literal


Action = Literal["hit", "stand", "double", "split", "surrender", "none"]


@dataclass(frozen=True)
class GameState:
    """
    Immutable snapshot of everything the strategy is allowed to see
    at a single decision point. Strategy receives this and nothing else.
    
    This is the contract between the simulator and any strategy.
    A strategy can never see the dealer's hole card, the remaining deck,
    or anything a real player wouldn't have access to at the table.
    """

    # --- Player hand state ---
    player_value: int           # current hand value after ace adjustment
    player_is_soft: bool        # True if hand contains ace counted as 11
    player_card_count: int      # number of cards in hand

    # --- Dealer state ---
    dealer_upcard: int          # dealer's visible card value

    # --- Legal actions ---
    can_hit: bool
    can_stand: bool
    can_double: bool
    can_split: bool
    can_surrender: bool

    # --- Counting info ---
    # Only populated if config.card_counting_allowed = True, else 0
    running_count: int = 0
    true_count: float = 0.0
    decks_remaining: float = 0.0

    # --- Session context ---
    bankroll: float = 0.0
    current_bet: float = 0.0
    hands_played: int = 0

    def legal_actions(self) -> list[Action]:
        """Returns list of currently legal actions."""
        actions: list[Action] = []
        if self.can_hit:
            actions.append("hit")
        if self.can_stand:
            actions.append("stand")
        if self.can_double:
            actions.append("double")
        if self.can_split:
            actions.append("split")
        if self.can_surrender:
            actions.append("surrender")
        return actions