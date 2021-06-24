import random

class Player: 
    def __init__(self):
        self.name = None
        self.money = None
        self.hand = [[]]
        self.soft = None

    def getName(self):
        return self.name

    def getMoney(self):
        return self.money

    def updateMoney(self, amount):
        self.money += amount

    def getTotal(self, i):
        total = 0
        self.soft = False
        for card in self.hand[i]:
            if (card == 1 and total + 11 <= 21):
                total += 11
                self.soft = True
            else:
                total += card
        return total

    def addCard(self, i, card):
        print("  " + self.name + " dealt a " + str(card))
        self.hand[i].append(card)

    def printHand(self, i):
        n = self.getTotal(i)
        s = ""
        if (i > 0 | len(self.hand) > 1):
            s = " " + str(i + 1)
        if (n == 21):
            print("  " + self.name + " hand" + s + ": 21")
        elif (self.soft):
            print("  " + self.name + " hand" + s + ": soft " + str(n))
        else:
            print("  " + self.name + " hand" + s + ": " + str(n))

    def clearHand(self):
        self.hand = [[]]

    def bust(self, i):
        return self.getTotal(i) > 21
    
    def blackjack(self, i):
        return self.getTotal(i) == 21
