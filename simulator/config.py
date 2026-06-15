from dataclasses import dataclass, field
from typing import Literal


@dataclass
class SimulatorConfig:
    """
    Full configuration for a Blackjack simulation environment.
    Defaults represent standard Las Vegas Strip rules.
    """

    # --- Deck settings ---
    num_decks: int = 6
    # Shuffle after every hand if True, otherwise shuffle at penetration threshold
    shuffle_every_round: bool = False
    # Fraction of shoe dealt before reshuffling (0.75 = shuffle when 75% dealt)
    penetration: float = 0.75

    # --- Dealer rules ---
    # True = dealer hits soft 17 (worse for player), False = dealer stands.
    # Default is S17 (stand): this is the ruleset BasicStrategy's chart targets,
    # so the simulator's default config and its "optimal" reference agree.
    dealer_hits_soft_17: bool = False
    # True = dealer checks for blackjack before player acts
    dealer_peeks: bool = True

    # --- Payout rules ---
    # Blackjack payout multiplier: 1.5 = 3:2, 1.2 = 6:5
    blackjack_payout: float = 1.5

    # --- Player action rules ---
    # "any" = double on any two cards, "9-11" = only 9/10/11, "10-11" = only 10/11
    double_allowed: Literal["any", "9-11", "10-11"] = "any"
    double_after_split: bool = True
    max_splits: int = 3
    surrender_allowed: bool = False

    # --- Card counting ---
    # If False, strategy cannot access running count in GameState
    card_counting_allowed: bool = True

    # --- Session defaults ---
    starting_bankroll: float = 1000.0
    min_bet: float = 10.0
    max_bet: float = 500.0


# --- Preset configurations ---

def vegas_strip() -> SimulatorConfig:
    """Standard 6-deck rules — dealer STANDS on soft 17 (S17), 3:2 blackjack, DAS.
    This is the ruleset BasicStrategy's chart is tuned for, so it is the
    recommended config for generating decision data with a correct optimal
    reference. (tough_rules deliberately uses H17 and so deviates slightly.)"""
    return SimulatorConfig()


def single_deck() -> SimulatorConfig:
    """Single deck rules — the strong card-counting case.

    Deals to 50% penetration before reshuffling (NOT every round): the count
    must be allowed to build up across hands for counting to mean anything.
    Shuffling every round would reset the count each hand and make counting
    pointless. 50% on one deck guarantees >=27 cards at every hand start, so a
    hand can never exhaust the deck mid-play.
    """
    return SimulatorConfig(
        num_decks=1,
        shuffle_every_round=False,
        penetration=0.5,
        blackjack_payout=1.5,
        dealer_hits_soft_17=False,
    )


def liberal_rules() -> SimulatorConfig:
    """Most player-friendly rules — best possible conditions."""
    return SimulatorConfig(
        num_decks=2,
        dealer_hits_soft_17=False,
        blackjack_payout=1.5,
        double_allowed="any",
        double_after_split=True,
        surrender_allowed=True,
        card_counting_allowed=True,
    )


def tough_rules() -> SimulatorConfig:
    """Worst player conditions — 6:5 blackjack, many restrictions."""
    return SimulatorConfig(
        num_decks=6,
        dealer_hits_soft_17=True,
        blackjack_payout=1.2,
        double_allowed="10-11",
        double_after_split=False,
        max_splits=1,
        surrender_allowed=False,
        card_counting_allowed=False,
    )