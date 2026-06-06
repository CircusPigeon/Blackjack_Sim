from enum import Enum


class Play(Enum):
    STAND = 0
    HIT = 1
    DOUBLE = 2
    SPLIT = 3
    SURRENDER = 4
    INSURANCE = 5
