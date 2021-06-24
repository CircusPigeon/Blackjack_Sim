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
        self.guest1 = Guest(1, "DEALER")
        self.guest2 = Guest(2, "RANDOM")
        self.guest3 = Guest(3, "STAND")
        self.numGuests = 3
        self.players.append(self.guest1)
        self.players.append(self.guest2)
        self.players.append(self.guest3)
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
            self.deal(player, 0)
        for player in self.players:
            self.deal(player, 0)
        print("  ----")
        #Print players' hands
        for player in self.players:
            player.printHand(0)
        print("  ----")
        #Each guest makes a play
        for player in self.players:
            if (player.blackjack(0)):
                print("  " + player.getName() + " has blackjack!")
            else:
                self.makePlay(player)
                if (not player.bust(0) and not player.blackjack(0)):
                    print("  " + player.getName() + " end move total: " + str(player.getTotal(0)))
        print("  ----")
        #Determine results and exchange money
        for i in range(self.numGuests):
            player = self.players[i]            
            if (player.blackjack(0) and not self.dealer.blackjack(0)):
                print("  " + player.getName() + " won 1.5x their bet: +" + str((int) (1.5 * player.getBet())))
                self.transferMoney(player, (int) (1.5 * player.getBet()))
                player.countFactor(2.5)
            elif (player.bust(0) or player.getTotal(0) < self.dealer.getTotal(0)):
                print("  " + player.getName() + " lost their bet: -" + str(player.getBet()))
                self.transferMoney(player, -player.getBet())
            elif (self.dealer.bust(0) or player.getTotal(0) > self.dealer.getTotal(0)):
                print("  " + player.getName() + " won their bet: +" + str(player.getBet()))
                self.transferMoney(player, player.getBet())
                player.countFactor(2)
            elif (player.getTotal(0) == self.dealer.getTotal(0)):
                print("  " + player.getName() + " drew the dealer: 0")
                player.countFactor(1)
        for i in range(self.numGuests):
            player = self.players[i]
            print("  " + player.getName() + " expected value: " + str(player.getEV(self.numRound)))
        print("********")

    def deal(self, player, i):
        player.addCard(i, self.deck.pullTopCard())

    def transferMoney(self, player, amount):
        player.updateMoney(amount)
        self.dealer.updateMoney(-amount)

    def makePlay(self, player):
        endTurn = False
        while (not endTurn):
            play = player.getPlay(0)
            if (play == Play.STAND.value):
                self.stand(player)
            if (play == Play.HIT.value):
                self.hit(player, 0)
            if (play == Play.DOUBLE.value):
                self.double(player)
            if (play == Play.SPLIT.value):
                self.split(player)
            if (play == Play.SURRENDER.value):
                self.surrender(player)
            if (play == Play.INSURANCE.value):
                self.insurance(player)
            if (player.bust(0) or player.blackjack(0) or play == Play.STAND.value or play == Play.SURRENDER.value or play == Play.INSURANCE.value):
                endTurn = True

    def stand(self, player):
        print("  " + player.getName() + " made move: stand")

    def hit(self, player, i):
        print("  " + player.getName() + " made move: hit")
        self.deal(player, i)
        if (player.bust(i)):
            print("  Bust!")
        if (player.blackjack(i)):
            print("  Blackjack!")

    def double(self, player):
        print("  " + player.getName() + " made move: double")
    
    def split(self, player):
        print("  " + player.getName() + " made move: split")

    def surrender(self, player):
        print("  " + player.getName() + " made move: surrender")

    def insurance(self, player):
        print("  " + player.getName() + " made move: insurance")
