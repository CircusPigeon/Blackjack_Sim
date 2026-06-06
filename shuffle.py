"""Shuffle procedures as pluggable strategy objects.

A real casino hand-shuffle is a short sequence of imperfect riffles, strips, and
a cut. The riffle is modeled by the Gilbert-Shannon-Reeds (GSR) distribution --
the standard model of a human riffle. Bayer & Diaconis showed ~7 riffles are
needed to randomize a single 52-card deck; a 6-deck shoe needs more, yet casinos
use only 2-4 riffles. That deliberate under-randomization is what leaves
trackable structure ("slugs") in the shoe."""

import random


class Shuffle:
    name = "base"
    continuous = False          # True => the shoe is reshuffled every round (CSM)

    def shuffle(self, cards):
        raise NotImplementedError


class RandomShuffle(Shuffle):
    """The idealized, fully-random baseline."""
    name = "random"

    def shuffle(self, cards):
        random.shuffle(cards)


class CSM(Shuffle):
    """Continuous shuffle machine: dealt cards are returned after every round, so
    the shoe is effectively always a fresh random shoe. This destroys counting."""
    name = "csm"
    continuous = True

    def shuffle(self, cards):
        random.shuffle(cards)


def gsr_riffle(cards):
    """One Gilbert-Shannon-Reeds riffle, in place.

    Split the deck binomially, then drop from each packet with probability
    proportional to its remaining size (which makes every interleaving of the
    two packets equally likely)."""
    n = len(cards)
    k = sum(1 for _ in range(n) if random.random() < 0.5)   # Binomial(n, 1/2) split
    left = cards[:k]
    right = cards[k:]
    a, b = len(left), len(right)
    i = j = 0
    out = []
    while (i < a and j < b):
        if (random.random() < (a - i) / ((a - i) + (b - j))):
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    if (i < a):
        out.extend(left[i:])
    if (j < b):
        out.extend(right[j:])
    cards[:] = out


def strip(cards, min_p=3, max_p=8):
    """Strip/box: pull small packets off the top onto a new pile, which reverses
    the order of the packets while preserving order within each."""
    n = len(cards)
    packets = []
    i = 0
    while (i < n):
        size = random.randint(min_p, max_p)
        packets.append(cards[i:i + size])
        i += size
    out = []
    for p in reversed(packets):
        out.extend(p)
    cards[:] = out


def cut(cards, jitter=0.15):
    """Final cut near the middle."""
    n = len(cards)
    span = int(n * jitter)
    c = n // 2 + random.randint(-span, span)
    c = max(1, min(n - 1, c))
    cards[:] = cards[c:] + cards[:c]


class CasinoShuffle(Shuffle):
    """A configurable hand-shuffle procedure. By default: a few riffles, a strip,
    and a cut -- representative of a common 6-deck shoe shuffle."""
    name = "casino"

    def __init__(self, riffles=3, strips=1, procedure=None):
        if (procedure is not None):
            self.procedure = list(procedure)
        else:
            self.procedure = ["riffle"] * riffles + ["strip"] * strips + ["cut"]

    def shuffle(self, cards):
        for op in self.procedure:
            if (op == "riffle"):
                gsr_riffle(cards)
            elif (op == "strip"):
                strip(cards)
            elif (op == "cut"):
                cut(cards)


def make_shuffler(name):
    if (name == "casino"):
        return CasinoShuffle()
    if (name == "csm"):
        return CSM()
    return RandomShuffle()
