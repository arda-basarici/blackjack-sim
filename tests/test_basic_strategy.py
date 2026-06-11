import pytest
from simulator.game_state import GameState
from strategies.basic_strategy import BasicStrategy


def hard_state(
    player_value: int,
    dealer_upcard: int,
    *,
    can_double: bool = True,
    can_surrender: bool = False,
) -> GameState:
    return GameState(
        player_value=player_value,
        player_is_soft=False,
        player_card_count=2,
        dealer_upcard=dealer_upcard,
        can_hit=True,
        can_stand=True,
        can_double=can_double,
        can_split=False,
        can_surrender=can_surrender,
    )


def soft_state(
    player_value: int,
    dealer_upcard: int,
    *,
    can_double: bool = True,
) -> GameState:
    return GameState(
        player_value=player_value,
        player_is_soft=True,
        player_card_count=2,
        dealer_upcard=dealer_upcard,
        can_hit=True,
        can_stand=True,
        can_double=can_double,
        can_split=False,
        can_surrender=False,
    )


def pair_state(pair_card_value: int, dealer_upcard: int) -> GameState:
    # A+A hand value is 12 (one ace as 11, one as 1) and is soft
    if pair_card_value == 11:
        total, is_soft = 12, True
    else:
        total, is_soft = pair_card_value * 2, False
    return GameState(
        player_value=total,
        player_is_soft=is_soft,
        player_card_count=2,
        dealer_upcard=dealer_upcard,
        can_hit=True,
        can_stand=True,
        can_double=True,
        can_split=True,
        can_surrender=False,
    )


strategy = BasicStrategy()


class TestHardHands:
    def test_hard_16_vs_10_hits_without_surrender(self):
        # Most beginners stand here; correct play is hit (or surrender if offered)
        assert strategy.decide(hard_state(16, 10)) == "hit"

    def test_hard_16_vs_10_surrenders_when_available(self):
        assert strategy.decide(hard_state(16, 10, can_surrender=True)) == "surrender"

    def test_hard_12_vs_2_hits(self):
        # Beginners stand on 12 fearing bust — correct play is hit vs dealer 2
        assert strategy.decide(hard_state(12, 2)) == "hit"

    def test_hard_12_vs_4_stands(self):
        assert strategy.decide(hard_state(12, 4)) == "stand"

    def test_hard_11_vs_6_doubles(self):
        assert strategy.decide(hard_state(11, 6)) == "double"

    def test_hard_11_vs_ace_hits(self):
        # Never double 11 vs dealer Ace (upcard=11)
        assert strategy.decide(hard_state(11, 11)) == "hit"

    def test_hard_10_vs_10_hits(self):
        # Beginners often double here; correct play is hit vs dealer 10
        assert strategy.decide(hard_state(10, 10)) == "hit"

    def test_hard_10_vs_6_doubles(self):
        assert strategy.decide(hard_state(10, 6)) == "double"

    def test_hard_9_vs_3_doubles(self):
        assert strategy.decide(hard_state(9, 3)) == "double"

    def test_hard_9_vs_2_hits(self):
        # 9 vs 2 is a hit, not a double — a common beginner mistake
        assert strategy.decide(hard_state(9, 2)) == "hit"

    def test_hard_17_stands_against_all_upcards(self):
        for dealer in range(2, 12):
            assert strategy.decide(hard_state(17, dealer)) == "stand"


class TestSoftHands:
    def test_soft_18_vs_9_hits(self):
        # Counterintuitive: 18 looks strong but the correct play vs 9 is hit
        assert strategy.decide(soft_state(18, 9)) == "hit"

    def test_soft_18_vs_2_stands(self):
        assert strategy.decide(soft_state(18, 2)) == "stand"

    def test_soft_18_vs_6_doubles(self):
        assert strategy.decide(soft_state(18, 6)) == "double"

    def test_soft_17_vs_6_doubles(self):
        assert strategy.decide(soft_state(17, 6)) == "double"

    def test_soft_17_vs_7_hits(self):
        # Soft 17 never stands — always hit or double
        assert strategy.decide(soft_state(17, 7)) == "hit"

    def test_soft_19_and_20_always_stand(self):
        for dealer in range(2, 12):
            assert strategy.decide(soft_state(19, dealer)) == "stand"
            assert strategy.decide(soft_state(20, dealer)) == "stand"


class TestPairs:
    def test_pair_of_aces_always_splits(self):
        for dealer in range(2, 12):
            assert strategy.decide(pair_state(11, dealer)) == "split"

    def test_pair_of_eights_always_splits(self):
        # Always split 8s — even vs dealer 10, surrender instinct is wrong here
        for dealer in range(2, 12):
            assert strategy.decide(pair_state(8, dealer)) == "split"

    def test_pair_of_tens_never_splits(self):
        # Never split 10s regardless of dealer upcard
        for dealer in range(2, 12):
            assert strategy.decide(pair_state(10, dealer)) == "stand"

    def test_pair_of_nines_stands_vs_7(self):
        # 9s vs 7: dealer is likely to make 17 — standing on 18 is correct
        assert strategy.decide(pair_state(9, 7)) == "stand"

    def test_pair_of_nines_splits_vs_8(self):
        assert strategy.decide(pair_state(9, 8)) == "split"


class TestFallbacks:
    def test_double_falls_back_to_hit_when_unavailable(self):
        # Hard 11 vs 6 wants double; without that option the next best is hit
        state = hard_state(11, 6, can_double=False)
        assert strategy.decide(state) == "hit"

    def test_surrender_falls_back_to_hit_when_unavailable(self):
        # Hard 16 vs 10 wants surrender; without it, hit is correct
        state = hard_state(16, 10, can_surrender=False)
        assert strategy.decide(state) == "hit"

    def test_soft_double_falls_back_to_hit(self):
        # Soft 17 vs 6 wants double; without that option, hit
        state = soft_state(17, 6, can_double=False)
        assert strategy.decide(state) == "hit"
