import random

class Deck: 
    def __init__(self, numPacks):
        self.numCards = numPacks * 52
        self.cards = [0] * self.numCards
    
    def fillDeck(self):
        for i in range(self.numCards):
            if (i % 13 + 1 > 10):
                self.cards[i] = 10
            else:
                self.cards[i] = i % 13 + 1

    def pullTopCard(self):
        self.numCards -= 1
        return self.cards.pop(0)

    def shuffle(self):
        for i in range(self.numCards):
            self.swapCards(i, random.randint(0, self.numCards - 1))
            
    def swapCards(self, i1, i2):
        temp = self.cards[i1]
        self.cards[i1] = self.cards[i2]
        self.cards[i2] = temp

    def printDeck(self):
        print(self.cards)