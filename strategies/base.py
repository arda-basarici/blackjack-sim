from abc import ABC, abstractmethod
from simulator.game_state import GameState, Action


class Strategy(ABC):
    """
    Abstract base class for all action strategies.
    
    A strategy receives a GameState and returns one Action.
    It cannot modify game state, access the deck, or see
    anything a real player wouldn't see at the table.
    
    To implement a new strategy:
        1. Subclass Strategy
        2. Implement decide()
        3. Pass an instance to the simulator
    
    Example:
        class AlwaysStand(Strategy):
            def decide(self, state: GameState) -> Action:
                return "stand"
    """

    @abstractmethod
    def decide(self, state: GameState) -> Action:
        """
        Given the current game state, return an action.
        Must return one of the legal actions in state.legal_actions().
        """
        ...

    def name(self) -> str:
        """Human readable strategy name for data recording."""
        return self.__class__.__name__


class BettingStrategy(ABC):
    """
    Abstract base class for all betting strategies.
    
    A betting strategy receives the current GameState and bankroll,
    and returns a bet amount. The simulator enforces min/max bet
    limits from config — betting strategy doesn't need to worry about that.
    
    To implement a new betting strategy:
        1. Subclass BettingStrategy
        2. Implement bet()
        3. Pass an instance to the session simulator
    
    Example:
        class AlwaysMinBet(BettingStrategy):
            def bet(self, state: GameState, bankroll: float) -> float:
                return 10.0
    """

    @abstractmethod
    def bet(self, state: GameState, bankroll: float) -> float:
        """
        Given the current game state and available bankroll,
        return the desired bet amount.
        Simulator will clamp this to config min_bet/max_bet.
        """
        ...

    def name(self) -> str:
        """Human readable betting strategy name for data recording."""
        return self.__class__.__name__

    def update(self, outcome: str) -> None:
        """Called after each hand. Override in stateful strategies."""
        pass

    def reset(self) -> None:
        """Called at session start. Override in stateful strategies."""
        pass