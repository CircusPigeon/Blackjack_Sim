from deck import Deck
from dealer import Dealer
from guest import Guest
from enum import Enum 

class Play (Enum):
    STAND = 0
    HIT = 1
    DOUBLE = 2
    SPLIT = 3
    SURRENDER = 4
    INSURANCE = 5

class Blackjack:
    def __init__(self):
        self.players = []
        self.dealer = Dealer()
        self.guest1 = Guest(1) #perfect basic strategy player
        self.guest2 = Guest(2) #random strategy player
        self.players.append(self.guest1)
        self.players.append(self.guest2)
        self.players.append(self.dealer)
        self.deck = Deck(6)
        self.deck.fillDeck()
        self.deck.shuffle()

    def run(self):
        #Deal two cards to each player
        for player in self.players:
            print("\tDealing cards to: " + player.getName())
            player.clearHand()
            player.addCard(self.deck.pullTopCard())
        for player in self.players:
            player.addCard(self.deck.pullTopCard())
        
        #Each guest makes a play
        print("")
        for player in self.players:
            print("\t" + player.getName() + " made move:", end =" ")
            play = player.getPlay()
            self.makePlay(play)
            if (player.bust()):
                print("\t" + player.getName() + " busted!")

    def makePlay(self, play):
        if (play == Play.STAND.value):
            self.stand()
        if (play == Play.HIT.value):
            self.hit()
        if (play == Play.DOUBLE.value):
            self.double()
        if (play == Play.SPLIT.value):
            self.split()
        if (play == Play.SURRENDER.value):
            self.split()
        if (play == Play.INSURANCE.value):
            self.insurance()

    def stand(self):
        print("Stand")

    def hit(self):
        print("Hit")

    def double(self):
        print("Double")
    
    def split(self):
        print("Split")

    def surrender(self):
        print("Surrender")

    def insurance(self):
        print("Insurance")