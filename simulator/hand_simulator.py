from dataclasses import dataclass, field
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

    # Legal actions available at this decision (the action space — lets the
    # RL agent reconstruct what was choosable, not just what was chosen).
    can_double: bool
    can_split: bool
    can_surrender: bool

    # Hand context
    decision_index: int          # 0 = first decision, 1 = second, etc.
    card_count_in_hand: int      # how many cards player had when deciding

    # Counting context
    running_count: int
    true_count: float
    decks_remaining: float

    # Outcome of the sub-hand this decision belongs to.
    # For a split, each sub-hand's records carry that sub-hand's own outcome;
    # the "split" decision itself carries the net result of all hands it spawned.
    final_player_value: int
    final_dealer_value: int
    outcome: str                 # "win", "lose", "push", "blackjack", "bust"
    is_win: int                  # 1 or 0
    payout: float                # actual payout multiplier

    # Session context
    bankroll_before: float
    bet_size: float


@dataclass
class SubResult:
    """
    Resolution of a single played-out hand. A normal hand has one;
    a split has one per resulting sub-hand. Bankroll = sum of payouts.
    """
    outcome: str
    payout: float
    final_player_value: int


@dataclass
class HandResult:
    """
    Summary of a completed hand (one dealt hand, which may become several
    sub-hands via splitting).

    `payout` is the TOTAL across all sub-hands — the bankroll delta.
    `outcome` summarises the dealt hand: for a single hand it is that hand's
    outcome; for a split it is the net (win/lose/push by sign of total payout).
    Per-sub-hand detail lives in `sub_results`.
    """
    hand_id: str
    outcome: str
    is_win: int
    payout: float
    final_player_value: int
    final_dealer_value: int
    decision_records: list[DecisionRecord]
    sub_results: list[SubResult] = field(default_factory=list)


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
            # With peek ON, a dealer blackjack was already resolved above, so
            # reaching here means the dealer has none. With peek OFF we never
            # looked — a mutual blackjack must PUSH, not pay 3:2.
            if not self._config.dealer_peeks and dealer_hand.is_blackjack():
                return self._resolve_hand(
                    hand_id, session_id, player_hand, dealer_hand,
                    dealer_upcard, [], bankroll, bet_size, "push"
                )
            return self._resolve_hand(
                hand_id, session_id, player_hand, dealer_hand,
                dealer_upcard, [], bankroll, bet_size, "blackjack"
            )

        # --- Player decision loop ---
        # Decisions are grouped per played-out hand so that, after a split,
        # each sub-hand's records are stamped with *that* sub-hand's outcome.
        # The "split" decision itself belongs to neither resulting hand; it is
        # collected separately and stamped with the net of both (Option A).
        decision_records: list[DecisionRecord] = []   # flat, in play order
        decision_index = 0
        split_count = 0                               # splits performed this hand
        player_hands = [player_hand]                  # queue; grows on split
        terminal_hands: list[tuple[Hand, list[DecisionRecord]]] = []
        split_records: list[DecisionRecord] = []

        while player_hands:
            current_hand = player_hands.pop(0)
            hand_records: list[DecisionRecord] = []

            while True:
                # Split aces get exactly one card — no hit, double, or resplit.
                if current_hand.from_split_aces:
                    action = "stand"
                    break

                state = self._build_state(
                    current_hand, dealer_upcard,
                    bankroll, bet_size, hands_played, split_count
                )
                action = self._strategy.decide(state)

                # Record this decision
                record = DecisionRecord(
                    hand_id=hand_id,
                    session_id=session_id,
                    strategy=self._strategy.name(),
                    config_id="",  # filled by experiment runner
                    player_value=state.player_value,
                    player_is_soft=state.player_is_soft,
                    dealer_upcard=dealer_upcard,
                    action=action,
                    can_double=state.can_double,
                    can_split=state.can_split,
                    can_surrender=state.can_surrender,
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
                )
                decision_records.append(record)
                hand_records.append(record)
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
                    # This decision is resolved against the net of both hands
                    # it spawns, not either one — pull it out of this hand's
                    # records and into the shared split bucket.
                    hand_records.remove(record)
                    split_records.append(record)
                    split_count += 1
                    card1, card2 = current_hand.cards
                    aces = card1.is_ace()        # splitting aces is special
                    new_hand1 = Hand(is_split_hand=True, from_split_aces=aces)
                    new_hand2 = Hand(is_split_hand=True, from_split_aces=aces)
                    new_hand1.add_card(card1)
                    new_hand1.add_card(self._deck.deal())
                    new_hand2.add_card(card2)
                    new_hand2.add_card(self._deck.deal())
                    player_hands.append(new_hand1)
                    player_hands.append(new_hand2)
                    break

                elif action == "surrender":
                    # NOTE: surrender resolves the whole dealt hand immediately.
                    # It is only legal on the opening two cards, so it cannot
                    # co-occur with a split in practice (surrender_allowed
                    # defaults off). Left as-is; not part of the split fix.
                    return self._resolve_hand(
                        hand_id, session_id, current_hand, dealer_hand,
                        dealer_upcard, decision_records, bankroll, bet_size, "surrender"
                    )

            # A split spawns new hands and is not itself terminal. Every other
            # exit — stand, double, or a bust — is a played-out hand to resolve,
            # busts included (previously dropped, silently leaking the loss).
            if action != "split":
                terminal_hands.append((current_hand, hand_records))

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

        # --- Resolve every played-out hand independently ---
        # Each sub-hand is scored against the dealer on its own; payouts sum to
        # the bankroll delta; each sub-hand's records carry its own outcome.
        final_dealer = dealer_hand.value()
        sub_results: list[SubResult] = []
        total_payout = 0.0

        for hand, records in terminal_hands:
            outcome = self._determine_outcome(hand, dealer_hand)
            payout = self._calculate_payout(outcome, bet_size, hand.is_doubled)
            is_win = 1 if outcome in ("win", "blackjack") else 0
            final_player = hand.value()

            for record in records:
                record.final_player_value = final_player
                record.final_dealer_value = final_dealer
                record.outcome = outcome
                record.is_win = is_win
                record.payout = payout

            sub_results.append(SubResult(outcome, payout, final_player))
            total_payout += payout

        total_payout = round(total_payout, 2)

        # Summary outcome for the dealt hand. A single hand reports its own
        # outcome; a split collapses to the net by sign of total payout (A).
        if split_records:
            net_outcome = (
                "win" if total_payout > 0
                else "lose" if total_payout < 0
                else "push"
            )
            net_is_win = 1 if net_outcome == "win" else 0
            for record in split_records:
                # The split decision spawned several hands, so it has no single
                # resolved value; the meaningful label is the net outcome/payout.
                record.final_player_value = 0
                record.final_dealer_value = final_dealer
                record.outcome = net_outcome
                record.is_win = net_is_win
                record.payout = total_payout
            summary_outcome = net_outcome
            summary_is_win = net_is_win
        else:
            summary_outcome = sub_results[0].outcome if sub_results else "bust"
            summary_is_win = 1 if summary_outcome in ("win", "blackjack") else 0

        return HandResult(
            hand_id=hand_id,
            outcome=summary_outcome,
            is_win=summary_is_win,
            payout=total_payout,
            final_player_value=sub_results[0].final_player_value if sub_results else 0,
            final_dealer_value=final_dealer,
            decision_records=decision_records,
            sub_results=sub_results,
        )

    def _build_state(
        self,
        hand: Hand,
        dealer_upcard: int,
        bankroll: float,
        bet_size: float,
        hands_played: int,
        splits_done: int = 0,
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
            can_split=self._can_split(hand, splits_done),
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

    def _can_split(self, hand: Hand, splits_done: int = 0) -> bool:
        """Splitting is allowed only on a pair, under the max-splits cap, and
        never on a split-ace hand (aces are split once and get one card each)."""
        if not hand.can_split():
            return False
        if hand.from_split_aces:
            return False
        if splits_done >= self._config.max_splits:
            return False
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
                can_double=False,
                can_split=False,
                can_surrender=False,
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
            sub_results=[SubResult(outcome, payout, final_player)],
        )