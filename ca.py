"""Composition-exact combinatorial analysis (the playing ceiling).

For a given remaining-shoe composition we compute the exact EV of each action
(stand / hit / double) by dynamic programming: the dealer's final-total
distribution and the player's optimal continuation are each memoized over
(total, soft) using the decision-time composition for draw probabilities (the
standard fast-CA approximation -- a hand draws few cards, so not depleting within
the hand is negligibly inexact).

We then sample decision states across all penetrations and measure how much
composition-perfect play beats fixed total-dependent basic strategy. That gap is
the theoretical PLAYING ceiling -- the headroom the EoR result said could only be
in play, not betting. Stand / hit / double / late-surrender are all modeled (the
surrender option respects the rule set, h17 and deck count). Splits are not
modeled (both sides play pairs by total), so this is the no-split playing ceiling."""

import numpy as np
from strategy import _hardPlay, _softPlay, _deviation
from play import Play

STAND = Play.STAND.value
HIT = Play.HIT.value
DOUBLE = Play.DOUBLE.value

_HILO = {1: -1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1}


def add_card(total, soft, r):
    if (r == 1):
        if (total + 11 <= 21):
            total += 11
            soft = True
        else:
            total += 1
    else:
        total += r
    if (soft and total > 21):
        total -= 10
        soft = False
    return total, soft


def hand_value(cards):
    total = sum(cards)
    soft = False
    if (1 in cards and total + 10 <= 21):
        total += 10
        soft = True
    return total, soft


def dealer_dist(upcard, p, h17):
    """Distribution over dealer final total: (p17, p18, p19, p20, p21, pbust)."""
    memo = {}

    def rec(total, soft):
        key = (total, soft)
        if (key in memo):
            return memo[key]
        if (total > 21):
            res = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
        elif (total >= 18 or (total == 17 and not (soft and h17))):
            a = [0.0] * 6
            a[total - 17] = 1.0
            res = tuple(a)
        else:
            a = [0.0] * 6
            for r in range(1, 11):
                if (p[r] > 0.0):
                    nt, ns = add_card(total, soft, r)
                    sub = rec(nt, ns)
                    pr = p[r]
                    for i in range(6):
                        a[i] += pr * sub[i]
            res = tuple(a)
        memo[key] = res
        return res

    if (upcard == 1):
        return rec(11, True)
    return rec(upcard, False)


def stand_ev(pt, d):
    win = d[5]                       # dealer bust
    lose = 0.0
    dealer_totals = (17, 18, 19, 20, 21)
    for i in range(5):
        if (pt > dealer_totals[i]):
            win += d[i]
        elif (pt < dealer_totals[i]):
            lose += d[i]
    return win - lose


def _policy_action(total, soft, upcard, can_double, policy, tc):
    # policy: "basic" or "hilo" (hilo = basic + Hi-Lo Illustrious-18 deviations).
    if (policy == "hilo" and not soft):
        dev = _deviation(total, upcard, tc, can_double)
        if (dev is not None):
            if (not (dev == DOUBLE and not can_double)):
                return dev
    return _softPlay(total, upcard, can_double) if soft else _hardPlay(total, upcard, can_double)


def node_value(total, soft, can_double, p, dout, upcard, policy, tc, memo):
    key = (total, soft, can_double)
    if (key in memo):
        return memo[key]
    if (total > 21):
        memo[key] = -1.0
        return -1.0
    es = stand_ev(total, dout)
    eh = 0.0
    for r in range(1, 11):
        pr = p[r]
        if (pr > 0.0):
            nt, ns = add_card(total, soft, r)
            eh += pr * (node_value(nt, ns, False, p, dout, upcard, policy, tc, memo)
                        if nt <= 21 else -1.0)
    ed = None
    if (can_double):
        ed = 0.0
        for r in range(1, 11):
            pr = p[r]
            if (pr > 0.0):
                nt, ns = add_card(total, soft, r)
                sev = -1.0 if nt > 21 else stand_ev(nt, dout)
                ed += pr * 2.0 * sev
    if (policy == "optimal"):
        val = max(es, eh, ed) if can_double else max(es, eh)
    else:
        act = _policy_action(total, soft, upcard, can_double, policy, tc)
        if (act == DOUBLE and can_double):
            val = ed
        elif (act == STAND):
            val = es
        else:
            val = eh
    memo[key] = val
    return val


def basic_surrenders(total, soft, up, h17):
    """Late-surrender basic-strategy decision, by total (mirrors strategy._surrender
    for hard non-pair hands -- the CA plays every hand by total)."""
    if (soft):
        return False
    if (total == 16):
        return up in (9, 10, 1)
    if (total == 15):
        return up == 10 or (h17 and up == 1)
    if (total == 17):
        return h17 and up == 1
    return False


def measure_playing_ceiling(n_samples=40000, numPacks=6, h17=True, seed=0,
                            rem_lo=0, rem_hi=None, cancel=None, surrender=False):
    rng = np.random.default_rng(seed)
    full = np.zeros(11)
    deck = []
    for r in range(1, 10):
        deck += [r] * (numPacks * 4)
        full[r] = numPacks * 4
    deck += [10] * (numPacks * 16)
    full[10] = numPacks * 16
    deck = np.array(deck)
    n = len(deck)
    cut = int(n * 0.75)
    if (rem_hi is None):
        rem_hi = cut
    hilo_w = np.array([0] + [_HILO[r] for r in range(1, 11)], dtype=float)

    opt_over_basic = 0.0
    hilo_over_basic = 0.0
    opt_over_hilo = 0.0
    oob_sq = 0.0
    hob_sq = 0.0
    deviate = 0
    counted = 0
    for _i in range(n_samples):
        if (cancel is not None and (_i & 2047) == 0):
            cancel()
        rng.shuffle(deck)
        removed = int(rng.integers(rem_lo, rem_hi))
        c1, c2, up = int(deck[removed]), int(deck[removed + 1]), int(deck[removed + 2])
        rest = deck[removed + 3:]
        comp = np.bincount(rest, minlength=11).astype(float)
        N = comp.sum()
        if (N < 20):
            continue
        total, soft = hand_value([c1, c2])
        if (total == 21):
            continue                            # natural: no decision
        p = comp / N
        tc = float((hilo_w * (full - comp)).sum()) / (N / 52.0)
        dout = dealer_dist(up, p, h17)
        ev_o = node_value(total, soft, True, p, dout, up, "optimal", tc, {})
        ev_b = node_value(total, soft, True, p, dout, up, "basic", tc, {})
        ev_h = node_value(total, soft, True, p, dout, up, "hilo", tc, {})
        if (surrender):
            # Late surrender (first decision only): optimal forfeits 0.5 whenever
            # playing it out is worse; basic / Hi-Lo follow the fixed surrender chart.
            ev_o = max(ev_o, -0.5)
            if (basic_surrenders(total, soft, up, h17)):
                ev_b = -0.5
                ev_h = -0.5
        d_ob = ev_o - ev_b
        d_hb = ev_h - ev_b
        opt_over_basic += d_ob
        hilo_over_basic += d_hb
        opt_over_hilo += (ev_o - ev_h)
        oob_sq += d_ob * d_ob
        hob_sq += d_hb * d_hb
        if (d_ob > 1e-9):
            deviate += 1
        counted += 1

    mob = opt_over_basic / counted
    mhb = hilo_over_basic / counted
    return {
        "opt_over_basic_pct": 100.0 * mob,
        "hilo_over_basic_pct": 100.0 * mhb,
        "opt_over_hilo_pct": 100.0 * opt_over_hilo / counted,
        "opt_over_basic_se": 100.0 * (max(oob_sq / counted - mob * mob, 0.0) / counted) ** 0.5,
        "hilo_over_basic_se": 100.0 * (max(hob_sq / counted - mhb * mhb, 0.0) / counted) ** 0.5,
        "deviate_frac": deviate / counted,
        "n": counted,
    }
