from dataclasses import dataclass
from enum import Enum
import random
from simulator.counting import CountingSystem 


class Suit(Enum):
    HEARTS = "Hearts"
    DIAMONDS = "Diamonds"
    CLUBS = "Clubs"
    SPADES = "Spades"


class Rank(Enum):
    TWO   = 2
    THREE = 3
    FOUR  = 4
    FIVE  = 5
    SIX   = 6
    SEVEN = 7
    EIGHT = 8
    NINE  = 9
    TEN   = 10
    JACK  = 11   # temporary unique values
    QUEEN = 12
    KING  = 13
    ACE   = 14

    def value_in_blackjack(self) -> int:
        """Blackjack value — face cards are 10, ace is 11."""
        if self in (Rank.JACK, Rank.QUEEN, Rank.KING):
            return 10
        if self == Rank.ACE:
            return 11
        return self.value

    def is_ace(self) -> bool:
        return self == Rank.ACE


@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

    def value(self) -> int:
        return self.rank.value_in_blackjack()

    def is_ace(self) -> bool:
        return self.rank.is_ace()

    def __str__(self) -> str:
        return f"{self.rank.name.capitalize()} of {self.suit.value}"


class Deck:
    def __init__(self, num_decks: int = 6, counting_system: "CountingSystem | None" = None):
        self.num_decks = num_decks
        self._counting_system = counting_system
        self._cards: list[Card] = []
        self._dealt_count: int = 0
        self.build()

    def build(self) -> None:
        """Build and shuffle a fresh shoe."""
        self._cards = [
            Card(rank, suit)
            for _ in range(self.num_decks)
            for suit in Suit
            for rank in Rank
        ]
        random.shuffle(self._cards)
        self._dealt_count = 0
        if self._counting_system:
            self._counting_system.reset()

    def deal(self) -> Card:
        """Deal one card from the top of the shoe."""
        if self.cards_remaining() == 0:
            raise RuntimeError("Deck is empty — reshuffle before dealing.")
        card = self._cards.pop()
        self._dealt_count += 1
        if self._counting_system:
            self._counting_system.update(card)
        return card

    @property
    def running_count(self) -> int:
        """Current running count. 0 if no counting system attached."""
        if self._counting_system:
            return self._counting_system.count
        return 0

    @property
    def true_count(self) -> float:
        """Running count normalized by decks remaining. 0 if no counting system."""
        if self._counting_system:
            decks_remaining = self.cards_remaining() / 52
            if decks_remaining == 0:
                return 0.0
            return self._counting_system.count / decks_remaining
        return 0.0

    def cards_remaining(self) -> int:
        return len(self._cards)

    def penetration(self) -> float:
        """Fraction of shoe dealt. 0.0 = fresh, 1.0 = fully dealt."""
        total = self.num_decks * 52
        return self._dealt_count / total

    def needs_shuffle(self, threshold: float, shuffle_every_round: bool) -> bool:
        """Check if deck should be reshuffled based on config."""
        if shuffle_every_round:
            return True
        return self.penetration() >= threshold