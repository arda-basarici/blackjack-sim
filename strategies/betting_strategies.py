from simulator.game_state import GameState
from strategies.base import BettingStrategy


class FlatBetting(BettingStrategy):
    """
    Bets the same fixed amount every hand.
    The simplest betting strategy — used as betting baseline.
    Most basic strategy guides recommend flat betting.
    """

    def __init__(self, bet_size: float = 10.0) -> None:
        self._bet_size = bet_size

    def bet(self, state: GameState, bankroll: float) -> float:
        return self._bet_size

    def name(self) -> str:
        return "flat"


class MartingaleBetting(BettingStrategy):
    """
    Doubles bet after every loss, resets to base bet after a win.
    Theory: a win always recovers all previous losses plus base profit.
    Reality: losing streaks cause exponential bet growth — high bust risk.
    
    Classic example of a strategy that looks good short term
    but fails catastrophically over a long session.
    """

    def __init__(self, base_bet: float = 10.0) -> None:
        self._base_bet = base_bet
        self._current_bet = base_bet
        self._last_outcome: str | None = None

    def bet(self, state: GameState, bankroll: float) -> float:
        if self._last_outcome == "lose":
            self._current_bet *= 2
        else:
            self._current_bet = self._base_bet
        return self._current_bet

    def update(self, outcome: str) -> None:
        """Called by session simulator after each hand resolves."""
        self._last_outcome = outcome

    def reset(self) -> None:
        """Reset state at start of new session."""
        self._current_bet = self._base_bet
        self._last_outcome = None

    def name(self) -> str:
        return "martingale"


class AntiMartingaleBetting(BettingStrategy):
    """
    Doubles bet after every win, resets to base bet after a loss.
    Opposite of Martingale — rides winning streaks, cuts losses quickly.
    Less catastrophic than Martingale but gives back wins on losing hands.
    """

    def __init__(self, base_bet: float = 10.0, max_progression: int = 4) -> None:
        self._base_bet = base_bet
        self._current_bet = base_bet
        self._progression = 0
        self._max_progression = max_progression
        self._last_outcome: str | None = None

    def bet(self, state: GameState, bankroll: float) -> float:
        if self._last_outcome == "win" and self._progression < self._max_progression:
            self._current_bet *= 2
            self._progression += 1
        else:
            self._current_bet = self._base_bet
            self._progression = 0
        return self._current_bet

    def update(self, outcome: str) -> None:
        self._last_outcome = outcome

    def reset(self) -> None:
        self._current_bet = self._base_bet
        self._progression = 0
        self._last_outcome = None

    def name(self) -> str:
        return "anti_martingale"


class CountBasedBetting(BettingStrategy):
    """
    Scales bet size based on true count.
    Only meaningful when card_counting_allowed=True in config.
    
    Bet spread scales with true count:
        true_count <= 1  → min bet (count not favorable)
        true_count 2-3   → 2x base bet
        true_count 4-5   → 4x base bet
        true_count > 5   → max bet (strongly favorable deck)
    
    This is how real card counters vary their bets without
    being obvious — a 1-to-8 spread is common in practice.
    """

    def __init__(self, base_bet: float = 10.0) -> None:
        self._base_bet = base_bet

    def bet(self, state: GameState, bankroll: float) -> float:
        tc = state.true_count

        if tc <= 1:
            multiplier = 1
        elif tc <= 3:
            multiplier = 2
        elif tc <= 5:
            multiplier = 4
        else:
            multiplier = 8

        return self._base_bet * multiplier

    def name(self) -> str:
        return "count_based"