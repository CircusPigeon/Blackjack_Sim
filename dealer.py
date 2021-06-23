from player import Player

class Dealer (Player):
    def __init__(self):
        Player()
        self.name = "Dealer"
        self.money = 1000000

    def getShowcard(self):
        return self.hand[1]

    def getPlay(self):
        return 0