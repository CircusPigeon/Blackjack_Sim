from player import Player

class Dealer (Player):
    def __init__(self):
        Player.__init__(self)
        self.name = "Dealer"
        self.money = 1000000

    def getShowcard(self):
        return self.hand[0][1]

    def getPlay(self, i):
        if (self.getTotal(i) < 17 or (self.getTotal(i) == 17 and self.soft == True)):
            return 1
        return 0