from dataclasses import dataclass
from simulator.card import Deck
from simulator.hand import Hand
from simulator.config import SimulatorConfig
from simulator.game_state import GameState, Action
from strategies.base import Strategy


@dataclass
class DecisionRecord:
    """
    One row in decisions.csv.
    Captures the full context of a single decision point.
    """
    hand_id: str
    session_id: str
    strategy: str
    config_id: str

    # State at decision point
    player_value: int
    player_is_soft: bool
    dealer_upcard: int
    action: Action

    # Hand context
    decision_index: int          # 0 = first decision, 1 = second, etc.
    card_count_in_hand: int      # how many cards player had when deciding

    # Counting context
    running_count: int
    true_count: float
    decks_remaining: float

    # Outcome — same for all decisions in a hand
    final_player_value: int
    final_dealer_value: int
    outcome: str                 # "win", "lose", "push", "blackjack", "bust"
    is_win: int                  # 1 or 0
    payout: float                # actual payout multiplier

    # Session context
    bankroll_before: float
    bet_size: float


@dataclass
class HandResult:
    """
    Summary of a completed hand.
    Returned by HandSimulator.play_hand() to SessionSimulator.
    """
    hand_id: str
    outcome: str
    is_win: int
    payout: float
    final_player_value: int
    final_dealer_value: int
    decision_records: list[DecisionRecord]


class HandSimulator:
    """
    Orchestrates a single Blackjack hand from deal to resolution.
    
    Responsibilities:
    - Deal cards
    - Build GameState at each decision point
    - Ask strategy for action
    - Execute action
    - Play out dealer hand
    - Determine outcome
    - Record all decisions
    
    Does NOT track bankroll — that is SessionSimulator's responsibility.
    """

    def __init__(
        self,
        config: SimulatorConfig,
        deck: Deck,
        strategy: Strategy,
    ) -> None:
        self._config = config
        self._deck = deck
        self._strategy = strategy
        self._hand_counter = 0

    def play_hand(
        self,
        session_id: str,
        bankroll: float,
        bet_size: float,
        hands_played: int,
    ) -> HandResult:
        """
        Play one complete hand and return the result.
        """
        self._hand_counter += 1
        hand_id = f"{session_id}_h{self._hand_counter}"

        # --- Deal initial cards ---
        player_hand = Hand()
        dealer_hand = Hand()

        player_hand.add_card(self._deck.deal())
        dealer_hand.add_card(self._deck.deal())
        player_hand.add_card(self._deck.deal())
        dealer_hand.add_card(self._deck.deal())  # hole card — not visible to strategy

        dealer_upcard = dealer_hand.cards[0].value()

        # --- Check for dealer blackjack (peek) ---
        if self._config.dealer_peeks and dealer_hand.is_blackjack():
            if player_hand.is_blackjack():
                return self._resolve_hand(
                    hand_id, session_id, player_hand, dealer_hand,
                    dealer_upcard, [], bankroll, bet_size, "push"
                )
            return self._resolve_hand(
                hand_id, session_id, player_hand, dealer_hand,
                dealer_upcard, [], bankroll, bet_size, "lose"
            )

        # --- Check for player blackjack ---
        if player_hand.is_blackjack():
            return self._resolve_hand(
                hand_id, session_id, player_hand, dealer_hand,
                dealer_upcard, [], bankroll, bet_size, "blackjack"
            )

        # --- Player decision loop ---
        decision_records: list[DecisionRecord] = []
        decision_index = 0
        player_hands = [player_hand]  # list to handle splits
        final_hands: list[Hand] = []

        while player_hands:
            current_hand = player_hands.pop(0)

            while True:
                state = self._build_state(
                    current_hand, dealer_upcard,
                    bankroll, bet_size, hands_played
                )
                action = self._strategy.decide(state)

                # Record this decision
                decision_records.append(DecisionRecord(
                    hand_id=hand_id,
                    session_id=session_id,
                    strategy=self._strategy.name(),
                    config_id="",  # filled by experiment runner
                    player_value=state.player_value,
                    player_is_soft=state.player_is_soft,
                    dealer_upcard=dealer_upcard,
                    action=action,
                    decision_index=decision_index,
                    card_count_in_hand=current_hand.card_count(),
                    running_count=state.running_count,
                    true_count=state.true_count,
                    decks_remaining=state.decks_remaining,
                    final_player_value=0,   # filled after hand resolves
                    final_dealer_value=0,   # filled after hand resolves
                    outcome="",             # filled after hand resolves
                    is_win=0,               # filled after hand resolves
                    payout=0.0,             # filled after hand resolves
                    bankroll_before=bankroll,
                    bet_size=bet_size,
                ))
                decision_index += 1

                # --- Execute action ---
                if action == "hit":
                    current_hand.add_card(self._deck.deal())
                    if current_hand.is_bust():
                        break

                elif action == "stand":
                    break

                elif action == "double":
                    current_hand.add_card(self._deck.deal())
                    current_hand.is_doubled = True
                    break

                elif action == "split":
                    # Create two new hands from the pair
                    card1, card2 = current_hand.cards
                    new_hand1 = Hand(is_split_hand=True)
                    new_hand2 = Hand(is_split_hand=True)
                    new_hand1.add_card(card1)
                    new_hand1.add_card(self._deck.deal())
                    new_hand2.add_card(card2)
                    new_hand2.add_card(self._deck.deal())
                    player_hands.append(new_hand1)
                    player_hands.append(new_hand2)
                    break

                elif action == "surrender":
                    return self._resolve_hand(
                        hand_id, session_id, current_hand, dealer_hand,
                        dealer_upcard, decision_records, bankroll, bet_size, "surrender"
                    )

            if not current_hand.is_bust() and action != "split":
                final_hands.append(current_hand)

        # --- Dealer plays out ---
        while True:
            dealer_value = dealer_hand.value()
            dealer_soft = dealer_hand.is_soft()

            should_hit = (
                dealer_value < 17 or
                (dealer_value == 17 and dealer_soft and self._config.dealer_hits_soft_17)
            )

            if not should_hit:
                break
            dealer_hand.add_card(self._deck.deal())

        # --- Determine outcome for each final hand ---
        # Use first final hand for primary outcome recording
        if not final_hands:
            outcome = "bust"
        else:
            outcome = self._determine_outcome(final_hands[0], dealer_hand)

        return self._resolve_hand(
            hand_id, session_id, final_hands[0] if final_hands else player_hand,
            dealer_hand, dealer_upcard, decision_records,
            bankroll, bet_size, outcome
        )

    def _build_state(
        self,
        hand: Hand,
        dealer_upcard: int,
        bankroll: float,
        bet_size: float,
        hands_played: int,
    ) -> GameState:
        """Build GameState from current hand state."""
        decks_remaining = self._deck.cards_remaining() / 52

        return GameState(
            player_value=hand.value(),
            player_is_soft=hand.is_soft(),
            player_card_count=hand.card_count(),
            dealer_upcard=dealer_upcard,
            can_hit=True,
            can_stand=True,
            can_double=self._can_double(hand),
            can_split=self._can_split(hand),
            can_surrender=self._config.surrender_allowed and hand.card_count() == 2,
            running_count=self._deck.running_count if self._config.card_counting_allowed else 0,
            true_count=self._deck.true_count if self._config.card_counting_allowed else 0.0,
            decks_remaining=decks_remaining,
            bankroll=bankroll,
            current_bet=bet_size,
            hands_played=hands_played,
        )

    def _can_double(self, hand: Hand) -> bool:
        """Check if doubling is allowed based on config and hand state."""
        if hand.card_count() != 2:
            return False
        if hand.is_split_hand and not self._config.double_after_split:
            return False
        value = hand.value()
        rule = self._config.double_allowed
        if rule == "any":
            return True
        if rule == "9-11":
            return 9 <= value <= 11
        if rule == "10-11":
            return 10 <= value <= 11
        return False

    def _can_split(self, hand: Hand) -> bool:
        """Check if splitting is allowed based on config and hand state."""
        if not hand.can_split():
            return False
        # Count existing splits by checking is_split_hand
        # Simple approach — config.max_splits tracked externally if needed
        return True

    def _determine_outcome(self, player_hand: Hand, dealer_hand: Hand) -> str:
        """Compare final player and dealer values to determine outcome."""
        player_value = player_hand.value()
        dealer_value = dealer_hand.value()

        if player_hand.is_bust():
            return "bust"
        if dealer_hand.is_bust():
            return "win"
        if player_value > dealer_value:
            return "win"
        if player_value < dealer_value:
            return "lose"
        return "push"

    def _calculate_payout(self, outcome: str, bet_size: float, is_doubled: bool) -> float:
        """Calculate actual payout based on outcome."""
        multiplier = 2.0 if is_doubled else 1.0

        if outcome == "blackjack":
            return bet_size * self._config.blackjack_payout
        if outcome == "win":
            return bet_size * multiplier
        if outcome == "push":
            return 0.0
        if outcome == "surrender":
            return -bet_size * 0.5
        # bust or lose
        return -bet_size * multiplier

    def _resolve_hand(
        self,
        hand_id: str,
        session_id: str,
        player_hand: Hand,
        dealer_hand: Hand,
        dealer_upcard: int,
        decision_records: list[DecisionRecord],
        bankroll: float,
        bet_size: float,
        outcome: str,
    ) -> HandResult:
        payout = self._calculate_payout(outcome, bet_size, player_hand.is_doubled)
        is_win = 1 if outcome in ("win", "blackjack") else 0
        final_player = player_hand.value()
        final_dealer = dealer_hand.value()

        # If no decisions were made (blackjack, dealer blackjack, surrender on first card)
        # still record one row so the hand appears in the dataset
        if not decision_records:
            decision_records.append(DecisionRecord(
                hand_id=hand_id,
                session_id=session_id,
                strategy=self._strategy.name(),
                config_id="",
                player_value=final_player,
                player_is_soft=player_hand.is_soft(),
                dealer_upcard=dealer_upcard,
                action="none",          # no decision made
                decision_index=0,
                card_count_in_hand=player_hand.card_count(),
                running_count=self._deck.running_count if self._config.card_counting_allowed else 0,
                true_count=self._deck.true_count if self._config.card_counting_allowed else 0.0,
                decks_remaining=self._deck.cards_remaining() / 52,
                final_player_value=final_player,
                final_dealer_value=final_dealer,
                outcome=outcome,
                is_win=is_win,
                payout=payout,
                bankroll_before=bankroll,
                bet_size=bet_size,
            ))

        for record in decision_records:
            record.final_player_value = final_player
            record.final_dealer_value = final_dealer
            record.outcome = outcome
            record.is_win = is_win
            record.payout = payout

        return HandResult(
            hand_id=hand_id,
            outcome=outcome,
            is_win=is_win,
            payout=payout,
            final_player_value=final_player,
            final_dealer_value=final_dealer,
            decision_records=decision_records,
        )