from simulator.game_state import GameState, Action
from strategies.base import Strategy


# Basic Strategy lookup tables
# All tables are indexed by (player_value, dealer_upcard)
# dealer_upcard: 2-10, Ace=11

# Hard hand decisions (no ace counted as 11)
# H=hit, S=stand, D=double, R=surrender
_HARD: dict[int, dict[int, str]] = {
    4:  {2:"H",3:"H",4:"H",5:"H",6:"H",7:"H",8:"H",9:"H",10:"H",11:"H"},
    5:  {2:"H",3:"H",4:"H",5:"H",6:"H",7:"H",8:"H",9:"H",10:"H",11:"H"},
    6:  {2:"H",3:"H",4:"H",5:"H",6:"H",7:"H",8:"H",9:"H",10:"H",11:"H"},
    7:  {2:"H",3:"H",4:"H",5:"H",6:"H",7:"H",8:"H",9:"H",10:"H",11:"H"},
    8:  {2:"H",3:"H",4:"H",5:"H",6:"H",7:"H",8:"H",9:"H",10:"H",11:"H"},
    9:  {2:"H",3:"D",4:"D",5:"D",6:"D",7:"H",8:"H",9:"H",10:"H",11:"H"},
    10: {2:"D",3:"D",4:"D",5:"D",6:"D",7:"D",8:"D",9:"D",10:"H",11:"H"},
    11: {2:"D",3:"D",4:"D",5:"D",6:"D",7:"D",8:"D",9:"D",10:"D",11:"H"},
    12: {2:"H",3:"H",4:"S",5:"S",6:"S",7:"H",8:"H",9:"H",10:"H",11:"H"},
    13: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"H",8:"H",9:"H",10:"H",11:"H"},
    14: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"H",8:"H",9:"H",10:"H",11:"H"},
    15: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"H",8:"H",9:"H",10:"H",11:"R"},
    16: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"H",8:"H",9:"R",10:"R",11:"R"},
    17: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
    18: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
    19: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
    20: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
    21: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
}

# Soft hand decisions (ace counted as 11)
# Key is the non-ace card value
_SOFT: dict[int, dict[int, str]] = {
    2:  {2:"H",3:"H",4:"H",5:"D",6:"D",7:"H",8:"H",9:"H",10:"H",11:"H"},
    3:  {2:"H",3:"H",4:"H",5:"D",6:"D",7:"H",8:"H",9:"H",10:"H",11:"H"},
    4:  {2:"H",3:"H",4:"D",5:"D",6:"D",7:"H",8:"H",9:"H",10:"H",11:"H"},
    5:  {2:"H",3:"H",4:"D",5:"D",6:"D",7:"H",8:"H",9:"H",10:"H",11:"H"},
    6:  {2:"H",3:"D",4:"D",5:"D",6:"D",7:"H",8:"H",9:"H",10:"H",11:"H"},
    7:  {2:"S",3:"D",4:"D",5:"D",6:"D",7:"S",8:"S",9:"H",10:"H",11:"H"},
    8:  {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
    9:  {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
}

# Pair splitting decisions
# Key is the card value of each card in the pair
_PAIRS: dict[int, dict[int, str]] = {
    2:  {2:"P",3:"P",4:"P",5:"P",6:"P",7:"P",8:"H",9:"H",10:"H",11:"H"},
    3:  {2:"P",3:"P",4:"P",5:"P",6:"P",7:"P",8:"H",9:"H",10:"H",11:"H"},
    4:  {2:"H",3:"H",4:"H",5:"P",6:"P",7:"H",8:"H",9:"H",10:"H",11:"H"},
    5:  {2:"D",3:"D",4:"D",5:"D",6:"D",7:"D",8:"D",9:"D",10:"H",11:"H"},
    6:  {2:"P",3:"P",4:"P",5:"P",6:"P",7:"H",8:"H",9:"H",10:"H",11:"H"},
    7:  {2:"P",3:"P",4:"P",5:"P",6:"P",7:"P",8:"H",9:"H",10:"H",11:"H"},
    8:  {2:"P",3:"P",4:"P",5:"P",6:"P",7:"P",8:"P",9:"P",10:"P",11:"P"},
    9:  {2:"P",3:"P",4:"P",5:"P",6:"P",7:"S",8:"P",9:"P",10:"S",11:"S"},
    10: {2:"S",3:"S",4:"S",5:"S",6:"S",7:"S",8:"S",9:"S",10:"S",11:"S"},
    11: {2:"P",3:"P",4:"P",5:"P",6:"P",7:"P",8:"P",9:"P",10:"P",11:"P"},
}

_ACTION_MAP: dict[str, Action] = {
    "H": "hit",
    "S": "stand",
    "D": "double",
    "P": "split",
    "R": "surrender",
}


class BasicStrategy(Strategy):
    """
    Mathematically optimal Blackjack strategy.
    Derived from combinatorial analysis — minimizes house edge.
    
    Decision priority:
        1. Pairs — check if hand can and should split
        2. Soft hands — hand contains ace counted as 11
        3. Hard hands — all other cases
    
    Fallback rules when preferred action isn't available:
        - Double not available → hit
        - Split not available → treat as hard hand
        - Surrender not available → hit
    """

    def decide(self, state: GameState) -> Action:
        dealer = state.dealer_upcard
        value = state.player_value

        # Priority 1: pairs
        if state.can_split:
            pair_value = 11 if state.player_is_soft else value // 2
            action_str = _PAIRS.get(pair_value, {}).get(dealer, "H")
            action = _ACTION_MAP[action_str]
            if action == "split":
                return "split"
            # If table says split but we can't, fall through to soft/hard

        # Priority 2: soft hands
        if state.player_is_soft:
            # Soft key is the non-ace card value (total - 11)
            soft_key = value - 11
            soft_key = max(2, min(soft_key, 9))
            action_str = _SOFT.get(soft_key, {}).get(dealer, "H")
            action = _ACTION_MAP[action_str]
            return self._resolve(action, state)

        # Priority 3: hard hands
        hard_key = max(4, min(value, 21))
        action_str = _HARD.get(hard_key, {}).get(dealer, "S")
        action = _ACTION_MAP[action_str]
        return self._resolve(action, state)

    def _resolve(self, action: Action, state: GameState) -> Action:
        """
        Apply fallback rules when preferred action isn't available.
        Double not available → hit
        Surrender not available → hit
        """
        if action == "double" and not state.can_double:
            return "hit"
        if action == "surrender" and not state.can_surrender:
            return "hit"
        return action

    def name(self) -> str:
        return "basic_strategy"