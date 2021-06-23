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
        self.guest2 = Guest(2) #random legal strategy player
        self.numGuests = 2
        self.players.append(self.guest1)
        self.players.append(self.guest2)
        self.players.append(self.dealer)
        self.deck = Deck(6)
        self.deck.fillDeck()
        self.deck.shuffle()
        self.numRound = 0

    def run(self):
        self.numRound += 1
        print("Round: " + str(self.numRound))
        #Print player's money and bets
        for player in self.players:
            print ("  " + player.getName() + " money: " + str(player.getMoney()))
            if (player.getName() != "Dealer"):
                player.calculateBet()
                print("  " + player.getName() + " bet: " + str(player.getBet()))
        print("  ----")
        #Deal two cards to each player
        for player in self.players:
            player.clearHand()
            self.deal(player)
        for player in self.players:
            self.deal(player)
        print("  ----")
        #Print players' hands
        for player in self.players:
            player.printHand()
        print("  ----")
        #Each guest makes a play
        for player in self.players:
            if (player.blackjack()):
                print("  " + player.getName() + " has blackjack!")
            else:
                self.makePlay(player)
                if ((not player.bust()) & (not player.blackjack())):
                    print("  End move total: " + str(player.getTotal()))
        print("  ----")
        #Determine results and exchange money
        for i in range(self.numGuests):
            player = self.players[i]            
            if (player.blackjack()):
                print("  " + player.getName() + " won 1.5x their bet: +" + str((int) (1.5 * player.getBet())))
                self.transferMoney(player, (int) (1.5 * player.getBet()))
                player.countFactor(2.5)
            elif (player.bust() | player.getTotal() < self.dealer.getTotal()):
                print("  " + player.getName() + " lost their bet: -" + str(player.getBet()))
                self.transferMoney(player, -player.getBet())
            elif (self.dealer.bust() | player.getTotal() > self.dealer.getTotal()):
                print("  " + player.getName() + " won their bet: +" + str(player.getBet()))
                self.transferMoney(player, player.getBet())
                player.countFactor(2)
            elif (player.getTotal() == self.dealer.getTotal()):
                print("  " + player.getName() + " tied the dealer: 0")
                player.countFactor(1)
        for i in range(self.numGuests):
            player = self.players[i]
            print("  " + player.getName() + " expected value: " + str(player.getEV(self.numRound)))
        print("********")

    def deal(self, player):
        player.addCard(self.deck.pullTopCard())

    def transferMoney(self, player, amount):
        player.updateMoney(amount)
        self.dealer.updateMoney(-amount)

    def makePlay(self, player):
        play = player.getPlay()
        if (play == Play.STAND.value):
            self.stand(player)
        if (play == Play.HIT.value):
            self.hit(player)
        if (play == Play.DOUBLE.value):
            self.double(player)
        if (play == Play.SPLIT.value):
            self.split(player)
        if (play == Play.SURRENDER.value):
            self.surrender(player)
        if (play == Play.INSURANCE.value):
            self.insurance(player)

    def stand(self, player):
        print("  " + player.getName() + " made move: stand")

    def hit(self, player):
        print("  " + player.getName() + " made move: hit")
        self.deal(player)
        if (player.bust()):
            print("  Bust!")
        if (player.blackjack()):
            print("  Blackjack!")

    def double(self, player):
        print("  " + player.getName() + " made move: double")
    
    def split(self, player):
        print("  " + player.getName() + " made move: split")

    def surrender(self, player):
        print("  " + player.getName() + " made move: surrender")

    def insurance(self, player):
        print("  " + player.getName() + " made move: insurance")