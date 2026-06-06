class Player:
    def __init__(self):
        self.name = None
        self.money = None
        self.hand = [[]]          # a list of hands (more than one after a split)
        self.handDone = [False]   # per-hand "no more actions" flag (split aces)
        self.surrendered = [False]  # per-hand late-surrender flag
        self.soft = None          # set as a side effect of getTotal()

    def getName(self):
        return self.name

    def getMoney(self):
        return self.money

    def updateMoney(self, amount):
        self.money += amount

    def getTotal(self, i):
        total = sum(self.hand[i])
        self.soft = False
        # Count one ace as 11 only if it fits; otherwise every ace stays 1.
        # (Two aces as 11 would be 22, so at most one can ever be soft.)
        if (1 in self.hand[i] and total + 10 <= 21):
            total += 10
            self.soft = True
        return total

    def addCard(self, i, card):
        self.hand[i].append(card)

    def isPair(self, i):
        return len(self.hand[i]) == 2 and self.hand[i][0] == self.hand[i][1]

    def handString(self, i):
        n = self.getTotal(i)
        if (n == 21 and len(self.hand[i]) == 2):
            desc = "blackjack"
        elif (self.soft):
            desc = "soft " + str(n)
        else:
            desc = str(n)
        label = (" " + str(i + 1)) if len(self.hand) > 1 else ""
        return "  " + self.name + " hand" + label + ": " + str(self.hand[i]) + " = " + desc

    def clearHand(self):
        self.hand = [[]]
        self.handDone = [False]
        self.surrendered = [False]

    def bust(self, i):
        return self.getTotal(i) > 21

    def blackjack(self, i):
        return self.getTotal(i) == 21
