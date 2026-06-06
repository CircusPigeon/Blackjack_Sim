"""The detection / 'heat' game.

A real counter isn't beaten by the math -- they're beaten by the pit. We model
the casino as estimating the player's bet-vs-count ramp slope from a running
(EWMA) regression of bet on true count, and backing the player off once that
estimated slope gets too steep. The player chooses a ramp aggressiveness (and,
optionally, camouflage 'cover' bets).

The tension: a steeper ramp earns more per hand but is detected sooner. The
quantity that matters is therefore total profit *until backoff*, and it is
maximized at an intermediate aggressiveness -- ramp as hard as you can while
staying under the radar. This is the EV-optimal play under a heat budget.

Reuses the calibrated per-unit outcomes (result is bet-size-independent), so a
session is a fast resample rather than a re-deal."""

import numpy as np


def simulate_heat(calib, slope, pivot=1.0, min_bet=1.0, max_bet=60.0, p_cover=0.0, cover_bet=None,
                  alpha=0.04, threshold=2.0, width=0.5, base_rate=0.12, warmup=25,
                  maxHands=2000, M=8000, seed=0):
    rng = np.random.default_rng(seed)
    tc_s = calib["tc"]
    rpu_s = calib["rpu"]
    n = len(rpu_s)
    if (cover_bet is None):
        cover_bet = max_bet

    profit = np.zeros(M)
    length = np.zeros(M, dtype=np.int64)
    alive = np.ones(M, dtype=bool)
    backed = np.zeros(M, dtype=bool)

    # Casino's EWMA accumulators for the regression slope of bet on true count.
    mb = np.zeros(M)
    mc = np.zeros(M)
    mbc = np.zeros(M)
    mcc = np.zeros(M)
    nobs = np.zeros(M)

    for _ in range(maxHands):
        if (not alive.any()):
            break
        idx = rng.integers(0, n, M)
        tc = tc_s[idx]
        rpu = rpu_s[idx]

        # Player ramp (units), optionally overridden by a camouflage cover bet.
        # A cover bet is a big bet placed at a LOW count (tc < pivot), which is
        # the opposite of what a counter does -- it drags the casino's estimated
        # bet/count slope back down, at the cost of a big bet on a bad hand.
        bet = np.clip(min_bet + slope * np.maximum(0.0, tc - pivot), min_bet, max_bet)
        if (p_cover > 0.0):
            cover = (rng.random(M) < p_cover) & (tc < pivot)
            bet = np.where(cover, cover_bet, bet)

        profit += np.where(alive, bet * rpu, 0.0)
        length += alive

        a = alpha
        mb = np.where(alive, (1 - a) * mb + a * bet, mb)
        mc = np.where(alive, (1 - a) * mc + a * tc, mc)
        mbc = np.where(alive, (1 - a) * mbc + a * bet * tc, mbc)
        mcc = np.where(alive, (1 - a) * mcc + a * tc * tc, mcc)
        nobs += alive

        cov = mbc - mb * mc
        varc = np.maximum(mcc - mc * mc, 1e-6)
        slope_est = cov / varc
        p_backoff = base_rate / (1.0 + np.exp(-(slope_est - threshold) / width))
        bo = alive & (nobs > warmup) & (rng.random(M) < p_backoff)
        backed |= bo
        alive = alive & ~bo

    ev_per_hand = float(profit.sum() / max(1, length.sum()))
    return {
        "mean_profit": float(profit.mean()),
        "mean_length": float(length.mean()),
        "ev_per_hand": ev_per_hand,
        "p_backed": float(backed.mean()),
    }


def aggressiveness_sweep(calib, slopes, **kw):
    """(slope, ev_per_hand, mean_length, mean_total_profit, p_backed) per ramp."""
    rows = []
    for s in slopes:
        r = simulate_heat(calib, slope=s, **kw)
        rows.append((s, r["ev_per_hand"], r["mean_length"], r["mean_profit"], r["p_backed"]))
    return rows
