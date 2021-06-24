import random

class Deck: 
    def __init__(self, numPacks):
        self.numCards = numPacks * 52
        self.cards = [0] * self.numCards
    
    def getNumCards(self):
        return len(self.cards)

    def fillDeck(self):
        for i in range(self.numCards):
            if (i % 13 + 1 > 10):
                self.cards[i] = 10
            else:
                self.cards[i] = i % 13 + 1

    def pullTopCard(self):
        card = self.cards.pop(0)
        if (len(self.cards) == 0):
            print("  *sOut of cards, reshuffling")
            self.cards = [0] * self.numCards
            self.fillDeck()
            self.shuffle()
        return card

    def shuffle(self):
        for i in range(self.numCards):
            self.swapCards(i, random.randint(0, self.numCards - 1))
            
    def swapCards(self, i1, i2):
        temp = self.cards[i1]
        self.cards[i1] = self.cards[i2]
        self.cards[i2] = temp

    def printDeck(self):
        print(self.cards)