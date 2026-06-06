from player import Player


class Dealer (Player):
    def __init__(self, hitSoft17=True):
        Player.__init__(self)
        self.name = "Dealer"
        self.money = 1000000
        self.hitSoft17 = hitSoft17

    def getShowcard(self):
        return self.hand[0][1]

    # Dealer hits to 17, and hits soft 17 only under H17 rules. The extra args
    # keep the signature uniform with Guest (the dealer never uses them).
    def getPlay(self, i, upcard, trueCount, canDouble, canSplit, canSurrender):
        total = self.getTotal(i)
        if (total < 17 or (total == 17 and self.soft and self.hitSoft17)):
            return 1
        return 0
