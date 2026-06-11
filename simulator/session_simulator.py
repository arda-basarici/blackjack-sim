import uuid
from dataclasses import dataclass
from simulator.card import Deck
from simulator.config import SimulatorConfig
from simulator.counting import CountingSystem
from simulator.hand_simulator import HandSimulator, DecisionRecord
from strategies.base import Strategy, BettingStrategy
from simulator.game_state import GameState


@dataclass
class SessionRecord:
    """
    One row in sessions.csv.
    Summary of a complete playing session.
    """
    session_id: str
    config_id: str
    strategy: str
    betting_strategy: str

    # Bankroll tracking
    starting_bankroll: float
    ending_bankroll: float
    peak_bankroll: float
    lowest_bankroll: float
    net_profit: float
    roi: float                  # (ending - starting) / starting * 100

    # Session stats
    hands_played: int
    went_bust: bool
    hands_won: int
    hands_lost: int
    hands_pushed: int
    hands_blackjack: int
    win_rate: float             # hands_won / hands_played

    # Counting context
    final_running_count: int
    final_true_count: float


class SessionSimulator:
    """
    Orchestrates a full playing session with bankroll tracking.
    Uses HandSimulator internally for each hand.

    Responsibilities:
    - Track bankroll across hands
    - Ask betting strategy for bet size before each hand
    - Notify stateful betting strategies of outcomes
    - Reshuffle deck when needed
    - Record session summary
    - Collect all decision records from all hands

    Does NOT know about strategies internals —
    only calls decide() and bet() interfaces.
    """

    def __init__(
        self,
        config: SimulatorConfig,
        strategy: Strategy,
        betting_strategy: BettingStrategy,
        counting_system: CountingSystem | None = None,
        config_id: str = "",
    ) -> None:
        self._config = config
        self._strategy = strategy
        self._betting_strategy = betting_strategy
        self._config_id = config_id
        self._deck = Deck(
            num_decks=config.num_decks,
            counting_system=counting_system,
        )
        self._hand_simulator = HandSimulator(config, self._deck, strategy)

    def run_session(
        self,
        num_hands: int,
        starting_bankroll: float | None = None,
    ) -> tuple[SessionRecord, list[DecisionRecord]]:
        """
        Run a full session of num_hands hands.
        Returns session summary and all decision records.
        """
        session_id = str(uuid.uuid4())[:8]
        bankroll = starting_bankroll or self._config.starting_bankroll

        # Session tracking
        peak_bankroll = bankroll
        lowest_bankroll = bankroll
        hands_won = 0
        hands_lost = 0
        hands_pushed = 0
        hands_blackjack = 0
        all_decisions: list[DecisionRecord] = []

        # Reset stateful betting strategy
        if hasattr(self._betting_strategy, "reset"):
            self._betting_strategy.reset()

        for hand_num in range(num_hands):
            # Check bankroll
            if bankroll <= 0:
                break

            # Reshuffle if needed
            if self._deck.needs_shuffle(
                self._config.penetration,
                self._config.shuffle_every_round
            ):
                self._deck.build()

            # Get bet size from betting strategy
            state_for_bet = self._build_pre_hand_state(bankroll, hand_num)
            bet_size = self._betting_strategy.bet(state_for_bet, bankroll)

            # Clamp bet to config limits and available bankroll
            bet_size = max(self._config.min_bet, min(bet_size, self._config.max_bet))
            bet_size = min(bet_size, bankroll)

            # Play the hand
            result = self._hand_simulator.play_hand(
                session_id=session_id,
                bankroll=bankroll,
                bet_size=bet_size,
                hands_played=hand_num,
            )

            # Update bankroll
            bankroll += result.payout
            bankroll = round(bankroll, 2)

            # Track peaks
            peak_bankroll = max(peak_bankroll, bankroll)
            lowest_bankroll = min(lowest_bankroll, bankroll)

            # Update outcome counters
            if result.outcome == "blackjack":
                hands_blackjack += 1
                hands_won += 1
            elif result.outcome == "win":
                hands_won += 1
            elif result.outcome in ("lose", "bust", "surrender"):
                hands_lost += 1
            elif result.outcome == "push":
                hands_pushed += 1

            # Notify stateful betting strategies
            if hasattr(self._betting_strategy, "update"):
                self._betting_strategy.update(result.outcome)

            # Fill config_id on decision records
            for record in result.decision_records:
                record.config_id = self._config_id

            all_decisions.extend(result.decision_records)

        # Build session record
        hands_played = len(set(r.hand_id for r in all_decisions)) if all_decisions else 0
        win_rate = hands_won / max(hands_played, 1)
        net_profit = bankroll - (starting_bankroll or self._config.starting_bankroll)
        roi = (net_profit / (starting_bankroll or self._config.starting_bankroll)) * 100

        session_record = SessionRecord(
            session_id=session_id,
            config_id=self._config_id,
            strategy=self._strategy.name(),
            betting_strategy=self._betting_strategy.name(),
            starting_bankroll=starting_bankroll or self._config.starting_bankroll,
            ending_bankroll=bankroll,
            peak_bankroll=peak_bankroll,
            lowest_bankroll=lowest_bankroll,
            net_profit=net_profit,
            roi=roi,
            hands_played=hands_played,
            went_bust=bankroll <= 0,
            hands_won=hands_won,
            hands_lost=hands_lost,
            hands_pushed=hands_pushed,
            hands_blackjack=hands_blackjack,
            win_rate=win_rate,
            final_running_count=self._deck.running_count,
            final_true_count=self._deck.true_count,
        )

        return session_record, all_decisions

    def _build_pre_hand_state(self, bankroll: float, hands_played: int) -> "GameState":
        """
        Build a minimal GameState for betting strategy before hand starts.
        Player hand not yet dealt — only session context is available.
        """
        from simulator.game_state import GameState
        decks_remaining = self._deck.cards_remaining() / 52

        return GameState(
            player_value=0,
            player_is_soft=False,
            player_card_count=0,
            dealer_upcard=0,
            can_hit=False,
            can_stand=False,
            can_double=False,
            can_split=False,
            can_surrender=False,
            running_count=self._deck.running_count if self._config.card_counting_allowed else 0,
            true_count=self._deck.true_count if self._config.card_counting_allowed else 0.0,
            decks_remaining=decks_remaining,
            bankroll=bankroll,
            current_bet=0.0,
            hands_played=hands_played,
        )