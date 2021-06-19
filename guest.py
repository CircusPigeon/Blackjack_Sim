from player import Player

class Guest (Player):
    def __init__(self):
        print("Guest joined!")
        Player()
        self.money = 1000
        #Can have variable strategy defined at beginning
        #Has more play options than dealer (split, double, surrender)
        #Makes bets
    
    def determineBet(self):
        return 50 #card-counting version tbd