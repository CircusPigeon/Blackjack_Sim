from player import Player

class Guest (Player):
    def __init__(self, num):
        Player.__init__(self)
        self.name = "Guest " + str(num)
        self.bet = None
        self.money = 1000
        self.factorTally = 0

    def getEV(self, numRounds):
        return float (self.factorTally) / numRounds 

    def countFactor(self, multiplier):
        self.factorTally += multiplier

    def calculateBet(self):
        self.bet = 50 #bet spread to be determined

    def getBet(self):
        return self.bet

    def getPlay(self):
        return 0