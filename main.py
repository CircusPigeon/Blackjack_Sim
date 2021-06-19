from deck import Deck
from dealer import Dealer
from guest import Guest

def main():
    print("Welcome to the blackjack sim!")
    dealer = Dealer()
    guest1 = Guest() #perfect basic strategy player
    guest2 = Guest() #random strategy player
    deck = Deck(6)
    deck.printDeck()
    deck.fillDeck()
    deck.printDeck()
    deck.shuffle()
    deck.printDeck()

main()