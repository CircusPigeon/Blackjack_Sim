"""Basic strategy (6-deck, double-after-split, late surrender) plus the hard-total
and doubling members of the Hi-Lo "Illustrious 18" count-based deviations.

Upcards are 1-10, where 1 is an Ace and 10 covers T/J/Q/K. Functions take the
acting player and a hand index and return a Play value (int). Whether the dealer
hits soft 17 is read from player.rules (it shifts a few surrender cells)."""

from play import Play

STAND = Play.STAND.value
HIT = Play.HIT.value
DOUBLE = Play.DOUBLE.value
SPLIT = Play.SPLIT.value
SURRENDER = Play.SURRENDER.value


def _hitSoft17(player):
    rules = getattr(player, "rules", None)
    if (rules):
        return rules.get("hitSoft17", True)
    return True


def basicPlay(player, i, upcard, canDouble, canSplit, canSurrender):
    total = player.getTotal(i)
    soft = player.soft
    if (canSurrender and not soft and _surrender(player, i, upcard, _hitSoft17(player))):
        return SURRENDER
    if (canSplit and player.isPair(i) and _pairSplit(player.hand[i][0], upcard)):
        return SPLIT
    if (soft):
        return _softPlay(total, upcard, canDouble)
    return _hardPlay(total, upcard, canDouble)


def countPlay(player, i, upcard, trueCount, canDouble, canSplit, canSurrender):
    total = player.getTotal(i)
    soft = player.soft
    # Index plays apply only to hard, non-pair totals. A None result means the
    # count does not trigger a deviation, so defer to basic strategy (which may
    # itself surrender).
    if (not soft and not player.isPair(i)):
        dev = _deviation(total, upcard, trueCount, canDouble)
        if (dev is not None):
            return dev
    return basicPlay(player, i, upcard, canDouble, canSplit, canSurrender)


def _surrender(player, i, up, hitSoft17):
    # Late surrender, H17 chart. Evaluated only on a fresh two-card hard hand.
    if (player.isPair(i) and player.hand[i][0] == 8):
        return up == 1 and hitSoft17          # 8,8 vs A (H17): surrender, don't split
    if (player.isPair(i)):
        return False
    total = player.getTotal(i)
    if (total == 16):
        return up in (9, 10, 1)
    if (total == 15):
        return up == 10 or (hitSoft17 and up == 1)
    if (total == 17):
        return hitSoft17 and up == 1          # 17 vs A (H17)
    return False


def _pairSplit(card, up):
    if (card == 1):          # A,A
        return True
    if (card == 10):         # T,T
        return False
    if (card == 9):
        return up in (2, 3, 4, 5, 6, 8, 9)
    if (card == 8):
        return True
    if (card == 7):
        return up in (2, 3, 4, 5, 6, 7)
    if (card == 6):
        return up in (2, 3, 4, 5, 6)
    if (card == 5):          # play as hard 10
        return False
    if (card == 4):
        return up in (5, 6)
    if (card in (2, 3)):
        return up in (2, 3, 4, 5, 6, 7)
    return False


def _softPlay(total, up, canDouble):
    if (total >= 20):                    # soft 20, 21
        return STAND
    if (total == 19):                    # A,8  (H17 doubles vs 6)
        if (up == 6 and canDouble):
            return DOUBLE
        return STAND
    if (total == 18):                    # A,7
        if (up in (2, 3, 4, 5, 6)):
            return DOUBLE if canDouble else STAND
        if (up in (7, 8)):
            return STAND
        return HIT
    if (total == 17):                    # A,6
        if (up in (3, 4, 5, 6)):
            return DOUBLE if canDouble else HIT
        return HIT
    if (total in (15, 16)):              # A,4 / A,5
        if (up in (4, 5, 6)):
            return DOUBLE if canDouble else HIT
        return HIT
    if (total in (13, 14)):              # A,2 / A,3
        if (up in (5, 6)):
            return DOUBLE if canDouble else HIT
        return HIT
    return HIT                           # soft 12 (A,A held)


def _hardPlay(total, up, canDouble):
    if (total >= 17):
        return STAND
    if (total in (13, 14, 15, 16)):
        return STAND if up in (2, 3, 4, 5, 6) else HIT
    if (total == 12):
        return STAND if up in (4, 5, 6) else HIT
    if (total == 11):                    # H17 doubles vs everything
        return DOUBLE if canDouble else HIT
    if (total == 10):
        if (up in (2, 3, 4, 5, 6, 7, 8, 9)):
            return DOUBLE if canDouble else HIT
        return HIT
    if (total == 9):
        if (up in (3, 4, 5, 6)):
            return DOUBLE if canDouble else HIT
        return HIT
    return HIT                           # 5-8


def _deviation(total, up, tc, canDouble):
    """Return a count-based override, or None to defer to basic strategy.

    The hard-total and doubling members of the Hi-Lo "Illustrious 18" index plays
    (Schlesinger), each tagged with its Hi-Lo index. Insurance (+3) and the two
    pair-split plays (10,10 v 5 / v 6) are not hard-total index plays this engine
    applies here. 11 v A (+1) is included for completeness but is a no-op in this
    H17 game, where basic already doubles 11 v A."""
    # Stiff totals: stand as the deck turns rich, hit as it turns poor.
    if (total == 16 and up == 10):
        return STAND if tc >= 0 else None        # 16 v T   index  0
    if (total == 16 and up == 9):
        return STAND if tc >= 5 else None        # 16 v 9   index +5
    if (total == 15 and up == 10):
        return STAND if tc >= 4 else None        # 15 v T   index +4
    if (total == 13 and up == 2):
        return HIT if tc < -1 else None          # 13 v 2   index -1
    if (total == 13 and up == 3):
        return HIT if tc < -2 else None          # 13 v 3   index -2
    if (total == 12 and up == 2):
        return STAND if tc >= 3 else None        # 12 v 2   index +3
    if (total == 12 and up == 3):
        return STAND if tc >= 2 else None        # 12 v 3   index +2
    if (total == 12 and up == 4):
        return HIT if tc < 0 else None           # 12 v 4   index  0
    if (total == 12 and up == 5):
        return HIT if tc < -2 else None          # 12 v 5   index -2
    if (total == 12 and up == 6):
        return HIT if tc < -1 else None          # 12 v 6   index -1
    # Strong totals: double when the deck is rich enough.
    if (total == 11 and up == 1):
        return DOUBLE if (tc >= 1 and canDouble) else None    # 11 v A  index +1
    if (total == 10 and up in (10, 1)):
        return DOUBLE if (tc >= 4 and canDouble) else None    # 10 v T/A index +4
    if (total == 9 and up == 2):
        return DOUBLE if (tc >= 1 and canDouble) else None    # 9 v 2   index +1
    if (total == 9 and up == 7):
        return DOUBLE if (tc >= 3 and canDouble) else None    # 9 v 7   index +3
    return None
