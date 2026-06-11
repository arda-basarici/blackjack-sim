import pytest
from simulator.card import Card, Rank, Suit
from simulator.hand import Hand


def card(rank: Rank) -> Card:
    return Card(rank=rank, suit=Suit.SPADES)


class TestHandValue:
    def test_hard_total_no_aces(self):
        hand = Hand()
        hand.add_card(card(Rank.SEVEN))
        hand.add_card(card(Rank.NINE))
        assert hand.value() == 16

    def test_face_cards_worth_ten(self):
        hand = Hand()
        hand.add_card(card(Rank.JACK))
        hand.add_card(card(Rank.QUEEN))
        assert hand.value() == 20

    def test_king_worth_ten(self):
        hand = Hand()
        hand.add_card(card(Rank.KING))
        hand.add_card(card(Rank.THREE))
        assert hand.value() == 13

    def test_ace_counts_as_eleven(self):
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.SIX))
        assert hand.value() == 17

    def test_ace_flips_to_one_to_avoid_bust(self):
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.KING))
        hand.add_card(card(Rank.FIVE))
        assert hand.value() == 16  # A(1) + K(10) + 5 = 16, not 26

    def test_two_aces_value(self):
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.ACE))
        assert hand.value() == 12  # A(11) + A(1) = 12, not 22

    def test_three_aces(self):
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.ACE))
        assert hand.value() == 13  # A(11) + A(1) + A(1) = 13


class TestSoftHand:
    def test_ace_and_seven_is_soft(self):
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.SEVEN))
        assert hand.is_soft() is True

    def test_hard_hand_is_not_soft(self):
        hand = Hand()
        hand.add_card(card(Rank.TEN))
        hand.add_card(card(Rank.SEVEN))
        assert hand.is_soft() is False

    def test_ace_forced_to_one_is_not_soft(self):
        # A + K + 5: ace must count as 1 to avoid bust → not soft
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.KING))
        hand.add_card(card(Rank.FIVE))
        assert hand.is_soft() is False

    def test_two_aces_is_soft(self):
        # A + A = 12: one ace still counts as 11 → soft
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.ACE))
        assert hand.is_soft() is True

    def test_two_aces_and_seven_is_soft(self):
        # A + A + 7 = 19: one ace as 11, one as 1 → still soft
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.SEVEN))
        assert hand.is_soft() is True


class TestBlackjack:
    def test_natural_blackjack_ace_and_king(self):
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.KING))
        assert hand.is_blackjack() is True

    def test_natural_blackjack_ace_and_ten(self):
        hand = Hand()
        hand.add_card(card(Rank.ACE))
        hand.add_card(card(Rank.TEN))
        assert hand.is_blackjack() is True

    def test_three_card_twenty_one_is_not_blackjack(self):
        # 21 on 3 cards is not a natural — important for payout difference
        hand = Hand()
        hand.add_card(card(Rank.SEVEN))
        hand.add_card(card(Rank.SEVEN))
        hand.add_card(card(Rank.SEVEN))
        assert hand.is_blackjack() is False

    def test_two_cards_not_twenty_one_is_not_blackjack(self):
        hand = Hand()
        hand.add_card(card(Rank.TEN))
        hand.add_card(card(Rank.NINE))
        assert hand.is_blackjack() is False


class TestBustAndSplit:
    def test_bust_over_21(self):
        hand = Hand()
        hand.add_card(card(Rank.KING))
        hand.add_card(card(Rank.QUEEN))
        hand.add_card(card(Rank.TWO))
        assert hand.is_bust() is True

    def test_exactly_21_is_not_bust(self):
        hand = Hand()
        hand.add_card(card(Rank.KING))
        hand.add_card(card(Rank.ACE))
        assert hand.is_bust() is False

    def test_can_split_matching_ranks(self):
        hand = Hand()
        hand.add_card(card(Rank.EIGHT))
        hand.add_card(card(Rank.EIGHT))
        assert hand.can_split() is True

    def test_can_split_face_cards_same_value(self):
        # King and Queen both worth 10 — splittable by value
        hand = Hand()
        hand.add_card(card(Rank.KING))
        hand.add_card(card(Rank.QUEEN))
        assert hand.can_split() is True

    def test_cannot_split_different_values(self):
        hand = Hand()
        hand.add_card(card(Rank.EIGHT))
        hand.add_card(card(Rank.NINE))
        assert hand.can_split() is False

    def test_cannot_split_three_cards(self):
        hand = Hand()
        hand.add_card(card(Rank.FIVE))
        hand.add_card(card(Rank.FIVE))
        hand.add_card(card(Rank.FIVE))
        assert hand.can_split() is False
