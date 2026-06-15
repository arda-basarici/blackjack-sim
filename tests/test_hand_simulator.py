"""
Split-resolution tests for HandSimulator.

These pin down the bug fixed at the Phase 2->3 boundary: on a split, both
hands must be scored independently — each sub-hand's win/loss reaches the
bankroll, and each sub-hand's decision records carry *that* hand's outcome
(not the first hand's). Before the fix, only final_hands[0] was resolved and
a busted split hand silently vanished.

The deck is stacked so every card is deterministic; the strategy is scripted
so the exact decision sequence is forced. No randomness.
"""

from simulator.card import Card, Rank, Suit, Deck
from simulator.config import SimulatorConfig
from simulator.game_state import GameState, Action
from simulator.hand_simulator import HandSimulator
from strategies.base import Strategy


def _card(rank: Rank) -> Card:
    return Card(rank=rank, suit=Suit.SPADES)


def _stacked_deck(deal_order: list[Rank]) -> Deck:
    """A deck that deals the given ranks in order. deal() pops from the end,
    so the list is reversed; a few filler cards guard against an unexpected
    extra deal turning a logic error into a confusing 'deck empty' crash."""
    deck = Deck(num_decks=1)
    filler = [_card(Rank.TWO)] * 4
    deck._cards = filler + [_card(r) for r in reversed(deal_order)]
    return deck


class ScriptedStrategy(Strategy):
    """Returns a fixed sequence of actions regardless of state."""

    def __init__(self, actions: list[Action]) -> None:
        self._actions = list(actions)
        self._i = 0

    def decide(self, state: GameState) -> Action:
        action = self._actions[self._i]
        self._i += 1
        return action


def _play(deal_order: list[Rank], actions: list[Action], bet: float = 10.0):
    config = SimulatorConfig()  # dealer stands on hard 17, peeks, 3:2
    deck = _stacked_deck(deal_order)
    sim = HandSimulator(config, deck, ScriptedStrategy(actions))
    return sim.play_hand(session_id="t", bankroll=1000.0, bet_size=bet, hands_played=0)


# Deal order for play_hand:
#   player1, dealer_up, player2, dealer_hole, then cards as dealt.


def test_split_scores_both_hands_independently():
    # 8,8 split. Sub-hand 1 -> 18 (win vs dealer 17); sub-hand 2 -> 13 (lose).
    deal = [
        Rank.EIGHT,   # player card 1
        Rank.SEVEN,   # dealer upcard
        Rank.EIGHT,   # player card 2  -> pair of 8s
        Rank.TEN,     # dealer hole    -> dealer 17, stands
        Rank.TEN,     # sub-hand 1 second card -> 18
        Rank.FIVE,    # sub-hand 2 second card -> 13
    ]
    result = _play(deal, actions=["split", "stand", "stand"], bet=10.0)

    # Two independent sub-results, one win one loss, summing to zero.
    assert len(result.sub_results) == 2
    assert {sr.outcome for sr in result.sub_results} == {"win", "lose"}
    assert sorted(sr.payout for sr in result.sub_results) == [-10.0, 10.0]

    # The bankroll delta is the SUM, not just the first hand's +10.
    assert result.payout == 0.0
    assert result.outcome == "push"  # Option A: net of the dealt hand

    # Each sub-hand's stand record carries its own outcome, not a shared one.
    stands = [r for r in result.decision_records if r.action == "stand"]
    assert len(stands) == 2
    by_value = {r.final_player_value: r for r in stands}
    assert by_value[18].outcome == "win" and by_value[18].payout == 10.0
    assert by_value[13].outcome == "lose" and by_value[13].payout == -10.0

    # The split decision itself is labelled with the net result.
    split_rec = next(r for r in result.decision_records if r.action == "split")
    assert split_rec.outcome == "push"
    assert split_rec.payout == 0.0
    assert split_rec.is_win == 0


def test_busted_split_hand_is_counted_not_dropped():
    # 8,8 split. Sub-hand 1 hits to a bust (24); sub-hand 2 stands on 18 (win).
    # Pre-fix, the busted hand never entered final_hands and its loss vanished,
    # leaving a phantom +10. Post-fix the bust is a real -10.
    deal = [
        Rank.EIGHT,   # player card 1
        Rank.SEVEN,   # dealer upcard
        Rank.EIGHT,   # player card 2  -> pair of 8s
        Rank.TEN,     # dealer hole    -> dealer 17, stands
        Rank.SIX,     # sub-hand 1 second card -> 14
        Rank.TEN,     # sub-hand 2 second card -> 18
        Rank.TEN,     # sub-hand 1 hit         -> 24, bust
    ]
    result = _play(deal, actions=["split", "hit", "stand"], bet=10.0)

    assert len(result.sub_results) == 2
    assert {sr.outcome for sr in result.sub_results} == {"bust", "win"}
    assert sorted(sr.payout for sr in result.sub_results) == [-10.0, 10.0]
    assert result.payout == 0.0  # not +10

    # The busted hand's own hit record is stamped as a loss.
    hit_rec = next(r for r in result.decision_records if r.action == "hit")
    assert hit_rec.outcome == "bust"
    assert hit_rec.payout == -10.0


def test_single_hand_unchanged():
    # Regression guard: a normal stand-and-win hand still resolves as before.
    deal = [
        Rank.TEN,     # player card 1
        Rank.TEN,     # dealer upcard
        Rank.NINE,    # player card 2  -> 19
        Rank.SEVEN,   # dealer hole    -> dealer 17, stands
    ]
    result = _play(deal, actions=["stand"], bet=10.0)

    assert len(result.sub_results) == 1
    assert result.outcome == "win"
    assert result.payout == 10.0
    assert len(result.decision_records) == 1
    assert result.decision_records[0].outcome == "win"
    assert result.decision_records[0].payout == 10.0
