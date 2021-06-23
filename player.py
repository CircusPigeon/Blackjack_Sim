import random

class Player: 
    def __init__(self):
        self.name = None
        self.money = None
        self.strategy = None #could be a class or 2/3D int array containing play to make given a hand and dealer show card if guest
        self.hand = []

    def getName(self):
        return self.name

    def getTotal(self):
        return self.hand[0] + self.hand[1]

    def addCard(self, card):
        self.hand.append(card)

    def clearHand(self):
        self.hand = []

    def bust(self):
        return self.getTotal > 21