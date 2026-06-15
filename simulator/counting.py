from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.card import Card


class CountingSystem(ABC):
    """Abstract base class for card counting systems."""

    @abstractmethod
    def update(self, card: "Card") -> None:
        """Update count when a card is dealt."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset count to initial state — called on deck rebuild."""
        ...

    @property
    @abstractmethod
    def count(self) -> int:
        """Current running count."""
        ...


class NoCount(CountingSystem):
    """Default — no counting. Used when card_counting_allowed=False."""

    def update(self, card: "Card") -> None:
        pass

    def reset(self) -> None:
        pass

    @property
    def count(self) -> int:
        return 0


class HiLoCount(CountingSystem):
    """
    Hi-Lo counting system.
    Low cards (2-6): +1 — good for player when removed
    High cards (10-A): -1 — bad for player when removed
    Neutral (7-9): 0
    Positive count = deck is rich in high cards = good for player.
    """

    def __init__(self) -> None:
        self._count: int = 0

    def update(self, card: "Card") -> None:
        value = card.value()
        if value >= 10:
            self._count -= 1
        elif value <= 6:
            self._count += 1

    def reset(self) -> None:
        self._count = 0

    @property
    def count(self) -> int:
        return self._count


class KOCount(CountingSystem):
    """
    Knock-Out (KO) counting system.
    Similar to Hi-Lo but 7 is also counted as +1.
    Unbalanced system — doesn't require true count conversion.
    """

    def __init__(self) -> None:
        self._count: int = 0

    def update(self, card: "Card") -> None:
        value = card.value()
        if value >= 10:
            self._count -= 1
        elif value <= 7:
            self._count += 1

    def reset(self) -> None:
        self._count = 0

    @property
    def count(self) -> int:
        return self._count


class OmegaIICount(CountingSystem):
    """
    Omega II counting system — more complex, more accurate.
    Multi-level system: cards have values of -2, -1, 0, +1, +2.
    """

    # Note: in Omega II the ace is counted as 0 (tracked separately as a
    # side count), not with the tens. card.value()==11 is the ace.
    _VALUES: dict[int, int] = {
        2: 1, 3: 1, 4: 2, 5: 2, 6: 2,
        7: 1, 8: 0, 9: -1, 10: -2, 11: 0
    }

    def __init__(self) -> None:
        self._count: int = 0

    def update(self, card: "Card") -> None:
        self._count += self._VALUES.get(card.value(), 0)

    def reset(self) -> None:
        self._count = 0

    @property
    def count(self) -> int:
        return self._count