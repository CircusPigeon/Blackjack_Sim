import random

class Player: 
    def __init__(self):
        self.name = None
        self.money = None
        self.strategy = None #could be a class or 2/3D int array containing play to make given a hand and dealer show card if guest
        self.hand = []
        self.soft = None

    def getName(self):
        return self.name

    def getMoney(self):
        return self.money

    def updateMoney(self, amount):
        self.money += amount

    def getTotal(self):
        total = 0
        self.soft = False
        for card in self.hand:
            if (card == 1 & total + 11 <= 21):
                total += 11
                self.soft = True
            else:
                total += card
        return total

    def addCard(self, card):
        print("  " + self.name + " dealt a " + str(card))
        self.hand.append(card)

    def printHand(self):
        n = self.getTotal()
        if (n == 21):
            print("  " + self.name + " hand: 21")
        elif (self.soft):
            print("  " + self.name + " hand: soft " + str(n))
        else:
            print("  " + self.name + " hand: " + str(n))

    def clearHand(self):
        self.hand = []

    def bust(self):
        return self.getTotal() > 21
    
    def blackjack(self):
        return self.getTotal() == 21
