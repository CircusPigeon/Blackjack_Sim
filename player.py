class Player: 
    def __init__(self):
        self.money = None
        self.strategy = None #could be a class or 2/3D int array containing play to make given a hand and dealer show card if guest
        self.hand = None #pair of ints
        self.play = None #enum int representing play to make (hit, stay, etc)

    def decidePlay(self):
        print("Deciding play...")