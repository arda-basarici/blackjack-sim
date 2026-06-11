from dataclasses import dataclass, field
from simulator.card import Card


@dataclass
class Hand:
    """
    Represents a Blackjack hand.
    Manages cards, calculates value with ace adjustment,
    and tracks hand state (soft, bust, blackjack).
    No game logic, no strategy — pure hand state.
    """
    cards: list[Card] = field(default_factory=list)
    is_split_hand: bool = False      # True if this hand resulted from a split
    is_doubled: bool = False         # True if player doubled down

    def add_card(self, card: Card) -> None:
        self.cards.append(card)

    def value(self) -> int:
        """
        Calculate hand value with ace adjustment.
        Aces start as 11, flip to 1 one at a time if bust.
        """
        total = sum(card.value() for card in self.cards)
        aces = sum(1 for card in self.cards if card.is_ace())

        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    def is_soft(self) -> bool:
        """
        True if hand contains an ace counted as 11.
        A soft hand can absorb one hit without busting.
        """
        total = sum(card.value() for card in self.cards)
        aces = sum(1 for card in self.cards if card.is_ace())

        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return aces > 0

    def is_bust(self) -> bool:
        return self.value() > 21

    def is_blackjack(self) -> bool:
        """Natural blackjack — exactly two cards, value 21."""
        return len(self.cards) == 2 and self.value() == 21

    def can_split(self) -> bool:
        """True if hand has exactly two cards of equal value."""
        return len(self.cards) == 2 and self.cards[0].value() == self.cards[1].value()

    def card_count(self) -> int:
        return len(self.cards)

    def __str__(self) -> str:
        cards_str = ", ".join(str(card) for card in self.cards)
        soft_str = " (soft)" if self.is_soft() else ""
        return f"[{cards_str}] = {self.value()}{soft_str}"