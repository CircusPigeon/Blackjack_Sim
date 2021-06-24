from blackjack import Blackjack

#To-dos:
#Figure out how to represent modifiable strategy tables
#Account for multiple split hands
#Implement every play option as well as subsequent plays
#Include card counting and bet spread

def main():
    print("Welcome to the blackjack sim!")
    game = Blackjack()
    for i in range(1000):
        game.run()

main()