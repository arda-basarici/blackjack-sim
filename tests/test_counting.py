import pytest
from simulator.card import Card, Rank, Suit
from simulator.counting import HiLoCount, KOCount, OmegaIICount


def card(rank: Rank) -> Card:
    return Card(rank=rank, suit=Suit.HEARTS)


def full_single_deck() -> list[Rank]:
    all_ranks = list(Rank)
    return all_ranks * 4  # 4 suits × 13 ranks = 52 cards


class TestHiLoCount:
    def test_low_cards_each_add_one(self):
        count = HiLoCount()
        for rank in [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX]:
            count.update(card(rank))
        assert count.count == 5

    def test_high_cards_each_subtract_one(self):
        count = HiLoCount()
        for rank in [Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]:
            count.update(card(rank))
        assert count.count == -5

    def test_neutral_cards_do_not_change_count(self):
        count = HiLoCount()
        for rank in [Rank.SEVEN, Rank.EIGHT, Rank.NINE]:
            count.update(card(rank))
        assert count.count == 0

    def test_known_sequence(self):
        # 2(+1) → K(-1) → 5(+1) → A(-1) → 8(0) = net 0
        count = HiLoCount()
        count.update(card(Rank.TWO))
        count.update(card(Rank.KING))
        count.update(card(Rank.FIVE))
        count.update(card(Rank.ACE))
        count.update(card(Rank.EIGHT))
        assert count.count == 0

    def test_balanced_over_full_single_deck(self):
        # Hi-Lo is balanced: 20 low cards (+20) cancel 20 high cards (-20)
        count = HiLoCount()
        for rank in full_single_deck():
            count.update(card(rank))
        assert count.count == 0

    def test_reset_clears_count(self):
        count = HiLoCount()
        count.update(card(Rank.TWO))
        count.update(card(Rank.THREE))
        count.reset()
        assert count.count == 0


class TestKOCount:
    def test_seven_increments_unlike_hilo(self):
        # KO counts 7 as +1; Hi-Lo treats 7 as neutral — this is the key difference
        count = KOCount()
        count.update(card(Rank.SEVEN))
        assert count.count == 1

    def test_known_sequence(self):
        # 3(+1) → 7(+1) → K(-1) → 9(0) → 6(+1) = net 2
        count = KOCount()
        count.update(card(Rank.THREE))
        count.update(card(Rank.SEVEN))
        count.update(card(Rank.KING))
        count.update(card(Rank.NINE))
        count.update(card(Rank.SIX))
        assert count.count == 2

    def test_unbalanced_over_full_single_deck(self):
        # KO is intentionally unbalanced: 24 low (+24) vs 20 high (-20) = +4 per deck
        # This is by design — no true count conversion needed
        count = KOCount()
        for rank in full_single_deck():
            count.update(card(rank))
        assert count.count == 4

    def test_reset_clears_count(self):
        count = KOCount()
        count.update(card(Rank.FIVE))
        count.reset()
        assert count.count == 0


class TestOmegaIICount:
    def test_four_five_six_worth_plus_two(self):
        count = OmegaIICount()
        count.update(card(Rank.FOUR))
        count.update(card(Rank.FIVE))
        count.update(card(Rank.SIX))
        assert count.count == 6

    def test_two_three_seven_worth_plus_one(self):
        count = OmegaIICount()
        count.update(card(Rank.TWO))
        count.update(card(Rank.THREE))
        count.update(card(Rank.SEVEN))
        assert count.count == 3

    def test_ten_and_face_cards_worth_minus_two(self):
        count = OmegaIICount()
        count.update(card(Rank.TEN))
        count.update(card(Rank.KING))
        assert count.count == -4

    def test_nine_worth_minus_one(self):
        count = OmegaIICount()
        count.update(card(Rank.NINE))
        assert count.count == -1

    def test_eight_is_neutral(self):
        count = OmegaIICount()
        count.update(card(Rank.EIGHT))
        assert count.count == 0

    def test_known_sequence(self):
        # 4(+2) → 9(-1) → 10(-2) → 2(+1) → 7(+1) = net +1
        count = OmegaIICount()
        count.update(card(Rank.FOUR))
        count.update(card(Rank.NINE))
        count.update(card(Rank.TEN))
        count.update(card(Rank.TWO))
        count.update(card(Rank.SEVEN))
        assert count.count == 1

    def test_reset_clears_count(self):
        count = OmegaIICount()
        count.update(card(Rank.FIVE))
        count.reset()
        assert count.count == 0
