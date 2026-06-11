from player import Player
from play import Play
from strategy import basicPlay, countPlay
import random

# Strategies that ramp their bet on a count signal (everyone else flat-bets).
BET_COUNTERS = ("COUNT", "TRACK", "ORACLE", "HIOPT2", "ZEN", "OMEGA2")
# Strategies that play count-based deviations on their own true count.
DEVIATORS = ("COUNT", "ORACLE", "HIOPT2", "ZEN", "OMEGA2")


class Guest (Player):
    def __init__(self, num, strat, unit=10):
        Player.__init__(self)
        self.name = "Guest " + str(num)
        self.money = 1000
        self.startMoney = 1000
        self.strategy = strat
        self.unit = unit
        # Bet-ramp parameters (counter only). Roughly Kelly-proportional: edge
        # rises ~0.5%/true count and crosses zero near TC +1, so bet ~1 unit per
        # true count above the ramp start, capped by the spread.
        self.minUnits = 1
        self.maxUnits = 20
        self.rampStart = 1.0
        self.slope = 1.0             # extra units per +1 true count above rampStart
        self.bet = unit
        self.bets = [unit]
        self.insuranceBet = 0
        self.totalWagered = 0
        self.rules = {}

        # Live heat / bankroll state (inert unless the engine turns it on).
        self.out = False             # left the table (barred or ruined)
        self.barred = False
        self.ruined = False
        self.handsPlayed = 0
        self.bankrollMode = False
        self.kellyFrac = 0.5
        self.minBet = 1.0
        self.maxBet = 500.0
        self.ruinLevel = 0.0
        self.edgePerTC = 0.005       # advantage ~ 0.5% per true count above pivot
        self.pivot = 1.0
        self.variance = 1.3
        self.hb = self.hc = self.hbc = self.hcc = self.hn = 0.0   # casino EWMA

    def calculateBet(self, signal):
        # COUNT ramps on the true count; TRACK ramps on the tracker's predicted
        # upcoming richness. Both use the same Kelly-ish ramp. Everyone else flat.
        if (self.out):
            self.bet = 0
            return
        if (self.bankrollMode and self.strategy in BET_COUNTERS):
            # Fractional Kelly of the current bankroll: bet ~ advantage/variance.
            adv = self.edgePerTC * (signal - self.pivot)
            if (adv <= 0.0):
                self.bet = self.minBet
            else:
                b = self.kellyFrac * (adv / self.variance) * self.money
                self.bet = max(self.minBet, min(b, self.maxBet, self.money))
            return
        if (self.strategy not in BET_COUNTERS):
            self.bet = self.unit
            return
        if (signal < self.rampStart):
            units = self.minUnits
        else:
            units = int(round(self.minUnits + self.slope * (signal - self.rampStart)))
            units = max(self.minUnits, min(units, self.maxUnits))
        self.bet = self.unit * units

    def getBet(self):
        return self.bet

    def wantsInsurance(self, trueCount):
        # Insure when the deck is ten-rich. The level-2 counts use the same +3
        # threshold: their tags are Hi-Lo-RMS-scaled, so the scale is shared.
        return (self.strategy in ("COUNT", "HIOPT2", "ZEN", "OMEGA2")
                and trueCount >= 3)

    def getProfit(self):
        return self.money - self.startMoney

    def getEdge(self):
        if (self.totalWagered == 0):
            return 0.0
        return float(self.getProfit()) / self.totalWagered

    def getPlay(self, i, upcard, trueCount, canDouble, canSplit, canSurrender):
        if (self.strategy == "DEALER"):
            if (self.getTotal(i) < 17 or (self.getTotal(i) == 17 and self.soft == True)):
                return Play.HIT.value
            return Play.STAND.value
        if (self.strategy == "RANDOM"):
            return random.randint(0, 1)
        if (self.strategy == "STAND"):
            return Play.STAND.value
        if (self.strategy == "BASIC"):
            return basicPlay(self, i, upcard, canDouble, canSplit, canSurrender)
        if (self.strategy == "COUNT"):
            return countPlay(self, i, upcard, trueCount, canDouble, canSplit, canSurrender)
        if (self.strategy == "TRACK"):
            # Shuffle tracking is a betting edge; play sound basic strategy.
            return basicPlay(self, i, upcard, canDouble, canSplit, canSurrender)
        if (self.strategy == "ORACLE"):
            # EoR-optimal betting; same Hi-Lo deviations as COUNT so only the
            # betting count differs (isolates the betting-accuracy gain).
            return countPlay(self, i, upcard, trueCount, canDouble, canSplit, canSurrender)
        if (self.strategy in ("HIOPT2", "ZEN", "OMEGA2")):
            # Level-2 counter: bets AND deviates on its own count. The engine
            # passes this strategy's true count in trueCount (Hi-Lo-scaled tags,
            # so the same index thresholds apply approximately).
            return countPlay(self, i, upcard, trueCount, canDouble, canSplit, canSurrender)
        return Play.STAND.value
