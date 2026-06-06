"""Shuffle tracking.

A shuffle tracker exploits the *sequence* correlation a weak shuffle leaves
behind (which plain counting ignores). It knows the pre-shuffle pile order and
the shuffle procedure, so it can predict where high-card "slugs" will land in the
next shoe and bet up as they are about to be dealt.

The prediction is linear: the expected Hi-Lo value at each deal position is a
fixed linear function of the pre-shuffle pile, captured by a position-transition
matrix T that depends only on the procedure. T is estimated once by Monte Carlo
(reusing the same shuffle code the dealer uses, so the model is exact), then each
shoe costs only one matrix-vector product.

This is an idealized 'full-knowledge' tracker: it sees the entire pre-shuffle
pile. That makes it an upper bound on what tracking can extract from a given
shuffle. A realistic tracker that only sees the discards is the obvious next
refinement."""

import random
import numpy as np

_CACHE = {}


def _signature(shuffler):
    proc = getattr(shuffler, "procedure", None)
    return (type(shuffler).__name__, tuple(proc) if proc is not None else None)


def transition_matrix(shuffler, n, trials=4000):
    """T[i, d] = P(card at pre-shuffle pile position i is dealt at step d).

    Built with the dealer's own shuffle code. The global RNG state is saved and
    restored so estimating T does not perturb the seeded game stream."""
    key = (_signature(shuffler), n, trials)
    if (key in _CACHE):
        return _CACHE[key]
    state = random.getstate()
    T = np.zeros((n, n))
    rows = np.arange(n)
    for _ in range(trials):
        cards = list(range(n))
        shuffler.shuffle(cards)
        arr = np.asarray(cards)
        invpos = np.empty(n, dtype=np.int64)
        invpos[arr] = rows               # invpos[label] = deck index after shuffle
        dealstep = (n - 1) - invpos      # cards are dealt from the top (end) first
        T[rows, dealstep] += 1.0
    T /= trials
    random.setstate(state)
    _CACHE[key] = T
    return T
