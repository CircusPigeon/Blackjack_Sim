from blackjack import Blackjack

#To-dos:
#Account for totals with multiple aces (can treat 1 7 7 as hard 15 instead of soft 25?)
#Figure out how to represent modifiable strategy tables
#Account for multiple split hands
#Implement every play option as well as subsequent plays
#Include card counting and bet spread

def main():
    print("Welcome to the blackjack sim!")
    game = Blackjack()
    for i in range(10000):
        game.run()

main()