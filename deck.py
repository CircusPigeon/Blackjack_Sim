import math
import random
import numpy as np
from shuffle import RandomShuffle

# Effects of removal: how much removing one card of each rank shifts the player's
# edge. The betting-optimal LINEAR count uses tags proportional to these, and
# Hi-Lo ({2-6:+1, 7-9:0, T/A:-1}) is a coarse integer rounding of them.
#
# These are derived from THIS engine, per rule set (precompute_eor.py): a flat-bet
# regression of realized edge on the remaining-shoe composition. They are balanced
# (frequency-weighted mean zero, so the running count is depth-neutral) and scaled
# to Hi-Lo's per-card RMS, so the EoR true count shares the Hi-Lo true-count scale
# and a single bet ramp treats both counts identically. Keyed by (hitSoft17,
# surrender) -- the rules that most change the weights.
EOR_WEIGHTS = {
    (True, True):   {1: -1.296, 2: 0.816, 3: 0.901, 4: 1.322, 5: 1.380, 6: 1.163, 7: 0.567, 8: -0.303, 9: -0.434, 10: -1.029},
    (True, False):  {1: -1.198, 2: 0.606, 3: 0.992, 4: 1.195, 5: 1.688, 6: 0.926, 7: 0.439, 8: 0.108, 9: -0.425, 10: -1.083},
    (False, True):  {1: -1.372, 2: 0.890, 3: 1.002, 4: 1.470, 5: 1.353, 6: 0.957, 7: 0.327, 8: -0.080, 9: -0.549, 10: -1.000},
    (False, False): {1: -1.560, 2: 0.635, 3: 1.294, 4: 0.905, 5: 1.145, 6: 1.239, 7: 0.566, 8: 0.073, 9: -0.057, 10: -1.060},
}
_EOR_DEFAULT = EOR_WEIGHTS[(True, True)]

# Classic Griffin values (a generic game), kept only for reference/comparison.
_EOR_BASE = {1: -0.61, 2: 0.38, 3: 0.44, 4: 0.55, 5: 0.69,
             6: 0.46, 7: 0.28, 8: 0.00, 9: -0.18, 10: -0.51}


def eor_tags(h17=True, surrender=True):
    """Engine-derived optimal linear betting weights for the given rule set."""
    return EOR_WEIGHTS.get((bool(h17), bool(surrender)), _EOR_DEFAULT)


# Level-2 counting systems, playable as the HIOPT2 / ZEN / OMEGA2 strategies.
# Raw integer tags (rank 1 = ace, 10 = T/J/Q/K), all balanced (frequency-weighted
# sum zero) so the true count is depth-neutral. They trade a little betting
# correlation for a better read on the PLAYING value of the cards.
COUNT_SYSTEMS = {
    "HIOPT2": {1: 0,  2: 1, 3: 1, 4: 2, 5: 2, 6: 1, 7: 1, 8: 0, 9: 0,  10: -2},
    "ZEN":    {1: -1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 1, 8: 0, 9: 0,  10: -2},
    "OMEGA2": {1: 0,  2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 1, 8: 0, 9: -1, 10: -2},
}
SYSTEM_LABELS = {"HIOPT2": "Hi-Opt II", "ZEN": "Zen", "OMEGA2": "Omega II"}

_FREQ = {r: (16.0 if r == 10 else 4.0) for r in range(1, 11)}


def _per_card_rms(tags):
    tot = sum(_FREQ.values())
    return math.sqrt(sum(_FREQ[r] / tot * tags[r] ** 2 for r in range(1, 11)))


_HILO_TAGS = {1: -1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1}

# The engine runs each system with its tags rescaled to Hi-Lo's per-card RMS
# (the same convention as the EoR weights), so every count lands on the shared
# Hi-Lo true-count scale and one bet ramp / one set of deviation indices applies.
SYSTEM_TAGS_SCALED = {
    name: {r: tags[r] * _per_card_rms(_HILO_TAGS) / _per_card_rms(tags)
           for r in range(1, 11)}
    for name, tags in COUNT_SYSTEMS.items()
}


class Deck:
    """A multi-deck shoe dealt without replacement, with a cut card and a Hi-Lo
    running count.

    The shoe is NOT rebuilt from rank order at each shuffle. Instead the unplayed
    remainder and the discards (in play order) are recombined and re-shuffled, so
    the previous shoe's order carries forward -- exactly as in a real game. After
    an initial "wash" the marginal composition stays uniform, so a weak shuffle
    does not bias a non-counter's hands; its weakness shows up only as sequential
    correlation across shoes, which is what a shuffle tracker exploits."""

    def __init__(self, numPacks, penetration=0.75, shuffler=None, track=False, eor=None):
        self.numPacks = numPacks
        self.numCards = numPacks * 52
        self.penetration = penetration
        self.cutCard = int(self.numCards * penetration)
        self.shuffler = shuffler if shuffler is not None else RandomShuffle()
        self.eor = eor if eor is not None else _EOR_DEFAULT   # EoR betting tags (rule-matched)
        self.cards = []
        self.discards = []
        self.roundMark = 0           # discard-pile length when the current round began
        self.runningCount = 0
        self.runningEoR = 0.0
        self.runningSys = {n: 0.0 for n in SYSTEM_TAGS_SCALED}
        self.tracking = track
        self.profile = None          # predicted Hi-Lo value per upcoming deal step
        self.T = None
        if (self.tracking):
            from tracker import transition_matrix
            self.T = transition_matrix(self.shuffler, self.numCards)
        self._initialShoe()

    def fillDeck(self):
        self.cards = []
        for i in range(self.numCards):
            rank = i % 13 + 1
            self.cards.append(10 if rank > 10 else rank)

    def _initialShoe(self):
        # New cards arrive in rank order; the casino wash breaks that up before
        # the first shuffle. Model the wash as one uniform mix.
        self.fillDeck()
        random.shuffle(self.cards)
        self.discards = []
        self.runningCount = 0
        self.runningEoR = 0.0
        self.runningSys = {n: 0.0 for n in SYSTEM_TAGS_SCALED}

    def reshuffle(self):
        # Recombine unplayed remainder + discards (play order). A tracker predicts
        # the next shoe from this pre-shuffle pile before it is shuffled.
        pile = self.cards + self.discards
        if (self.tracking):
            x = np.fromiter((self.countValue(c) for c in pile), dtype=float, count=len(pile))
            self.profile = x @ self.T          # E[Hi-Lo value at each deal step]
        self.discards = []
        self.shuffler.shuffle(pile)
        self.cards = pile
        self.runningCount = 0
        self.runningEoR = 0.0
        self.runningSys = {n: 0.0 for n in SYSTEM_TAGS_SCALED}

    def predictedTrueCount(self, window=15):
        # Forward-looking estimate of the next `window` cards' richness. High
        # cards carry Hi-Lo -1, so a negative predicted sum means a rich upcoming
        # slug -- flip the sign so positive = favorable, like a true count.
        if (self.profile is None):
            return 0.0
        d = len(self.discards)
        seg = self.profile[d:d + window]
        if (seg.size == 0):
            return 0.0
        return -float(seg.mean()) * 52.0

    def countValue(self, card):
        # Hi-Lo: 2-6 -> +1, 7-9 -> 0, T/A -> -1
        if 2 <= card <= 6:
            return 1
        if card == 1 or card == 10:
            return -1
        return 0

    def beginRound(self):
        # Mark where this round's dealing starts in the discard pile, so an
        # emergency reshuffle can tell completed-round cards (safe to return to
        # the shoe) from cards still live in the current hand.
        self.roundMark = len(self.discards)

    def _emergencyReshuffle(self):
        # The shoe ran dry mid-round (only happens in a single deck dealt deep,
        # where a round can start with fewer cards than it needs). Return just
        # the completed-round discards to the shoe and reshuffle; the current
        # round's cards stay out of play. The running count then reflects only
        # the cards still unseen out of the shoe (the live ones).
        live = self.discards[self.roundMark:]
        pile = self.cards + self.discards[:self.roundMark]
        self.shuffler.shuffle(pile)
        self.cards = pile
        self.discards = live
        self.roundMark = 0
        self.runningCount = sum(self.countValue(c) for c in live)
        self.runningEoR = float(sum(self.eor[c] for c in live))
        self.runningSys = {n: float(sum(t[c] for c in live))
                           for n, t in SYSTEM_TAGS_SCALED.items()}

    def pullTopCard(self, counted=True):
        # counted=False deals a card without updating the running count, used for
        # the dealer's hole card (a counter cannot see it yet).
        if (not self.cards):
            self._emergencyReshuffle()
        card = self.cards.pop()
        self.discards.append(card)
        if (counted):
            self.runningCount += self.countValue(card)
            self.runningEoR += self.eor[card]
            for n, t in SYSTEM_TAGS_SCALED.items():
                self.runningSys[n] += t[card]
        return card

    def applyCount(self, card):
        # Fold a previously-hidden card (the hole card) into the count once it is
        # turned face up.
        self.runningCount += self.countValue(card)
        self.runningEoR += self.eor[card]
        for n, t in SYSTEM_TAGS_SCALED.items():
            self.runningSys[n] += t[card]

    def needsReshuffle(self):
        # A CSM reshuffles every round; otherwise reshuffle at the cut card.
        if (self.shuffler.continuous):
            return True
        return (self.numCards - len(self.cards)) >= self.cutCard

    def getNumCards(self):
        return len(self.cards)

    def decksRemaining(self):
        return len(self.cards) / 52.0

    def getRunningCount(self):
        return self.runningCount

    def getTrueCount(self):
        decks = self.decksRemaining()
        if decks < 0.25:
            decks = 0.25
        return self.runningCount / decks

    def getEorTrueCount(self):
        # The effect-of-removal "true count": the best linear estimate of deck
        # favorability, normalized by decks remaining like the Hi-Lo true count.
        decks = self.decksRemaining()
        if decks < 0.25:
            decks = 0.25
        return self.runningEoR / decks

    def getSystemTrueCount(self, name):
        # True count for a level-2 system (HIOPT2 / ZEN / OMEGA2). The tags are
        # Hi-Lo-RMS-scaled, so this shares the Hi-Lo true-count scale.
        decks = self.decksRemaining()
        if decks < 0.25:
            decks = 0.25
        return self.runningSys[name] / decks

    def printDeck(self):
        print(self.cards)
