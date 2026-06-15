"""
Rule-fidelity tests for the post-audit simulator fixes:
  - split aces get exactly one card (no hit, no resplit)
  - the max_splits cap is enforced
  - a no-peek mutual blackjack pushes (and a lone player blackjack still pays)
  - basic strategy's soft-double "Ds" fallback and S17 chart cells

Decks are stacked and strategies scripted so every path is deterministic.
"""

from simulator.card import Rank
from simulator.config import SimulatorConfig
from simulator.game_state import GameState, Action
from simulator.hand_simulator import HandSimulator
from strategies.base import Strategy
from strategies.basic_strategy import BasicStrategy
from tests.test_hand_simulator import _stacked_deck


def _play(deal, strategy, config=None, bet=10.0):
    config = config or SimulatorConfig()
    deck = _stacked_deck(deal)
    sim = HandSimulator(config, deck, strategy)
    return sim.play_hand("t", 0.0, bet, 0)


class GreedySplit(Strategy):
    """Splits whenever the simulator says it's legal, otherwise stands."""
    def decide(self, state: GameState) -> Action:
        return "split" if state.can_split else "stand"


# ---------- split aces ----------

def test_split_aces_get_one_card_each():
    # A,A vs 7; dealer makes 17. Each ace receives exactly one card.
    deal = [Rank.ACE, Rank.SEVEN, Rank.ACE, Rank.TEN, Rank.FIVE, Rank.SIX]
    result = _play(deal, BasicStrategy())
    # Only the split decision is recorded — the ace hands take no further action,
    # even though basic strategy would otherwise hit a soft 16/17.
    assert [r.action for r in result.decision_records] == ["split"]
    assert len(result.sub_results) == 2
    # Two cards each: A,5 = 16 and A,6 = 17.
    assert sorted(sr.final_player_value for sr in result.sub_results) == [16, 17]


# ---------- max splits ----------

def test_max_splits_enforced():
    cfg = SimulatorConfig()  # max_splits = 3
    # An endless supply of 8s: every hand is a pair, so splitting only stops
    # when the cap is hit.
    deal = [Rank.EIGHT, Rank.SEVEN, Rank.EIGHT, Rank.TEN] + [Rank.EIGHT] * 12
    result = _play(deal, GreedySplit(), config=cfg)
    splits = [r for r in result.decision_records if r.action == "split"]
    assert len(splits) == cfg.max_splits                  # capped at 3 splits
    assert len(result.sub_results) == cfg.max_splits + 1  # -> 4 hands


# ---------- no-peek blackjack ----------

def test_no_peek_mutual_blackjack_pushes():
    cfg = SimulatorConfig(dealer_peeks=False)
    deal = [Rank.ACE, Rank.ACE, Rank.KING, Rank.KING]  # player A,K=BJ; dealer A,K=BJ
    result = _play(deal, BasicStrategy(), config=cfg)
    assert result.outcome == "push"
    assert result.payout == 0.0


def test_no_peek_lone_player_blackjack_pays():
    cfg = SimulatorConfig(dealer_peeks=False)
    deal = [Rank.ACE, Rank.SEVEN, Rank.KING, Rank.NINE]  # player A,K=BJ; dealer 16
    result = _play(deal, BasicStrategy(), config=cfg)
    assert result.outcome == "blackjack"
    assert result.payout == cfg.blackjack_payout * 10.0


# ---------- basic strategy: soft-double fallback + S17 chart ----------

def _st(pv, du, soft, can_double=True, can_split=False, can_surrender=False, cc=2):
    return GameState(
        player_value=pv, player_is_soft=soft, player_card_count=cc,
        dealer_upcard=du, can_hit=True, can_stand=True, can_double=can_double,
        can_split=can_split, can_surrender=can_surrender,
    )


def test_soft_double_falls_back_correctly():
    bs = BasicStrategy()
    assert bs.decide(_st(18, 3, True, can_double=True)) == "double"   # Ds, can double
    assert bs.decide(_st(18, 3, True, can_double=False)) == "stand"   # Ds -> stand
    assert bs.decide(_st(17, 4, True, can_double=False)) == "hit"     # soft 17 -> hit


def test_chart_targets_s17():
    bs = BasicStrategy()
    assert bs.decide(_st(11, 11, False)) == "hit"                       # 11 vs A (S17)
    assert bs.decide(_st(18, 2, True)) == "stand"                       # soft 18 vs 2 (S17)
    assert bs.decide(_st(15, 10, False, can_surrender=True)) == "surrender"
    assert bs.decide(_st(15, 11, False, can_surrender=True)) == "hit"   # no surr vs A (S17)
    assert bs.decide(_st(16, 11, False, can_surrender=True)) == "hit"   # no surr vs A (S17)
