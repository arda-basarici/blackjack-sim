import pytest
from simulator.game_state import GameState


def make_state(**overrides) -> GameState:
    defaults = dict(
        player_value=15,
        player_is_soft=False,
        player_card_count=2,
        dealer_upcard=7,
        can_hit=True,
        can_stand=True,
        can_double=False,
        can_split=False,
        can_surrender=False,
    )
    defaults.update(overrides)
    return GameState(**defaults)


class TestImmutability:
    def test_cannot_mutate_player_value(self):
        state = make_state(player_value=15)
        with pytest.raises((AttributeError, TypeError)):
            state.player_value = 20  # type: ignore[misc]

    def test_cannot_mutate_dealer_upcard(self):
        state = make_state(dealer_upcard=7)
        with pytest.raises((AttributeError, TypeError)):
            state.dealer_upcard = 10  # type: ignore[misc]

    def test_cannot_mutate_bankroll(self):
        state = make_state(bankroll=500.0)
        with pytest.raises((AttributeError, TypeError)):
            state.bankroll = 0.0  # type: ignore[misc]

    def test_cannot_mutate_true_count(self):
        state = make_state(true_count=3.5)
        with pytest.raises((AttributeError, TypeError)):
            state.true_count = 0.0  # type: ignore[misc]


class TestLegalActions:
    def test_hit_and_stand_included_when_available(self):
        state = make_state(can_hit=True, can_stand=True)
        legal = state.legal_actions()
        assert "hit" in legal
        assert "stand" in legal

    def test_double_included_only_when_available(self):
        with_double = make_state(can_double=True)
        without_double = make_state(can_double=False)
        assert "double" in with_double.legal_actions()
        assert "double" not in without_double.legal_actions()

    def test_split_included_only_when_available(self):
        with_split = make_state(can_split=True)
        without_split = make_state(can_split=False)
        assert "split" in with_split.legal_actions()
        assert "split" not in without_split.legal_actions()

    def test_surrender_included_only_when_available(self):
        with_surrender = make_state(can_surrender=True)
        without_surrender = make_state(can_surrender=False)
        assert "surrender" in with_surrender.legal_actions()
        assert "surrender" not in without_surrender.legal_actions()

    def test_all_actions_available(self):
        state = make_state(
            can_hit=True,
            can_stand=True,
            can_double=True,
            can_split=True,
            can_surrender=True,
        )
        assert set(state.legal_actions()) == {"hit", "stand", "double", "split", "surrender"}

    def test_legal_actions_count_matches_available_flags(self):
        state = make_state(can_hit=True, can_stand=True, can_double=True, can_split=False, can_surrender=False)
        assert len(state.legal_actions()) == 3
