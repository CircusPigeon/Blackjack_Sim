import random
import numpy as np
from shuffle import RandomShuffle

# Effects of removal (Griffin): how much removing one card of each rank shifts
# the player's edge. The betting-optimal LINEAR count uses tags proportional to
# these; Hi-Lo ({2-6:+1, 7-9:0, T/A:-1}) is just a coarse integer rounding. We
# scale to roughly Hi-Lo magnitude so the two counts ramp on the same scale.
EOR_SCALE = 2.2
_EOR_BASE = {1: -0.61, 2: 0.38, 3: 0.44, 4: 0.55, 5: 0.69,
             6: 0.46, 7: 0.28, 8: 0.00, 9: -0.18, 10: -0.51}
EOR = {c: _EOR_BASE[c] * EOR_SCALE for c in _EOR_BASE}


class Deck:
    """A multi-deck shoe dealt without replacement, with a cut card and a Hi-Lo
    running count.

    The shoe is NOT rebuilt from rank order at each shuffle. Instead the unplayed
    remainder and the discards (in play order) are recombined and re-shuffled, so
    the previous shoe's order carries forward -- exactly as in a real game. After
    an initial "wash" the marginal composition stays uniform, so a weak shuffle
    does not bias a non-counter's hands; its weakness shows up only as sequential
    correlation across shoes, which is what a shuffle tracker exploits."""

    def __init__(self, numPacks, penetration=0.75, shuffler=None, track=False):
        self.numPacks = numPacks
        self.numCards = numPacks * 52
        self.penetration = penetration
        self.cutCard = int(self.numCards * penetration)
        self.shuffler = shuffler if shuffler is not None else RandomShuffle()
        self.cards = []
        self.discards = []
        self.runningCount = 0
        self.runningEoR = 0.0
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

    def pullTopCard(self, counted=True):
        # counted=False deals a card without updating the running count, used for
        # the dealer's hole card (a counter cannot see it yet).
        card = self.cards.pop()
        self.discards.append(card)
        if (counted):
            self.runningCount += self.countValue(card)
            self.runningEoR += EOR[card]
        return card

    def applyCount(self, card):
        # Fold a previously-hidden card (the hole card) into the count once it is
        # turned face up.
        self.runningCount += self.countValue(card)
        self.runningEoR += EOR[card]

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

    def printDeck(self):
        print(self.cards)
