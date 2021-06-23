from player import Player

class Guest (Player):
    def __init__(self, n):
        Player()
        self.name = "Player " + str(n)
        self.money = 1000
    
    def getBet(self):
        return 50 #bet spread tbd

    def getPlay(self):
        return 0