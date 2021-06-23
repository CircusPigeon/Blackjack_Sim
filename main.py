from blackjack import Blackjack

def main():
    print("Welcome to the blackjack sim!")
    game = Blackjack()
    for i in range(10):
        print("Round: " + str(i))
        game.run()

main()