from player import Player

class Dealer (Player):
    def __init__(self):
        print("Dealer joined!")
        Player()
        self.money = 1000000
        self.showCard = None
        #Has predefined strategy based only on own hand
        #Can deal cards to guests
        #Gives or takes money to/from guests