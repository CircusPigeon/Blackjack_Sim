from blackjack import Blackjack

#To-dos:
#Modify hand to be a 2D list for splits
#Implement other play options and subsequent plays

def main():
    print("Welcome to the blackjack sim!")
    game = Blackjack()
    for i in range(10000):
        game.run()

main()