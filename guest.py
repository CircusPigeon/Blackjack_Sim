from player import Player
import random

class Guest (Player):
    def __init__(self, num, strat):
        Player.__init__(self)
        self.name = "Guest " + str(num)
        self.money = 1000
        self.strategy = strat
        self.bet = None
        self.factorTally = 0

    def getEV(self, numRounds):
        return float (self.factorTally) / numRounds 

    def countFactor(self, multiplier):
        self.factorTally += multiplier

    def calculateBet(self):
        self.bet = 50 #bet spread to be determined

    def getBet(self):
        return self.bet

    def getPlay(self, i):
        if (self.strategy == "DEALER"):
            if (self.getTotal(i) < 17 or (self.getTotal(i) == 17 and self.soft == True)):
                return 1
            return 0
        if (self.strategy == "RANDOM"):
            return random.randint(0, 1)
        if (self.strategy == "STAND"):
            return 0