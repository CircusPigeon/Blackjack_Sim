"""Bankroll / risk engine.

Card counting tells you your edge; the bankroll engine tells you whether you
survive the variance. We calibrate the counter's per-hand outcome distribution
once (result per unit bet, as a function of true count), then Monte-Carlo many
independent "trips" under fractional-Kelly bet sizing to measure risk of ruin,
probability of reaching a goal, growth, and drawdown.

Key fact that makes this exact and fast: the per-unit outcome (result / bet) does
not depend on how much was wagered -- doubling the bet doubles the result -- so
we can resample calibrated per-unit outcomes and scale each by whatever Kelly bet
the bankroll calls for, without re-dealing cards.

Bets are sized as a fraction of the *current* bankroll (resizing Kelly):
    bet = kellyFrac * edge(trueCount) / variance * bankroll,
clamped to the table limits."""

import os
import numpy as np

EDGE_LO = -6
EDGE_HI = 12


def load_or_make_calibration(path="results/calib.npz", rounds=1000000):
    """Load the cached COUNT calibration, or run it once and cache it."""
    if (os.path.exists(path)):
        d = np.load(path)
        return {"true_count": d["tc"], "bet": d["bet"], "result": d["result"]}
    from config import Config
    from experiment import run_experiment
    g = run_experiment(Config(rounds=rounds, strategies=("COUNT",), shuffle="random"),
                       record=True)
    rec = g.records
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez(path, tc=rec["true_count"], bet=rec["bet"], result=rec["result"])
    return rec


def calibrate(records):
    """Build the per-unit outcome model from a recorded COUNT run."""
    tc = np.asarray(records["true_count"], dtype=float)
    bet = np.asarray(records["bet"], dtype=float)
    result = np.asarray(records["result"], dtype=float)
    rpu = result / bet                                  # per-unit outcome
    buckets = np.clip(np.floor(tc).astype(int), EDGE_LO, EDGE_HI)
    edge_arr = np.zeros(EDGE_HI - EDGE_LO + 1)
    for b in range(EDGE_LO, EDGE_HI + 1):
        m = buckets == b
        if (m.any()):
            edge_arr[b - EDGE_LO] = rpu[m].mean()
    ev_hand = float(result.mean())                      # avg units won per hand
    sd_hand = float(result.std())                       # SD of units per hand
    edge_bw = float(result.sum() / bet.sum())           # edge per unit wagered (the real edge)
    return {
        "tc": tc,
        "rpu": rpu,
        "edge_arr": edge_arr,
        "var_unit": float(rpu.var()),
        "edge_bw": edge_bw,
        "sd_unit": float(rpu.std()),                    # SD per unit bet
        "n0": (sd_hand / ev_hand) ** 2 if ev_hand > 0 else float("inf"),
    }


def _edge_of(tc, edge_arr):
    b = np.clip(np.floor(tc).astype(int), EDGE_LO, EDGE_HI) - EDGE_LO
    return edge_arr[b]


def simulate_trips(calib, kellyFrac=0.5, B0=2000.0, table_min=1.0, table_max=200.0,
                   ruin_frac=0.5, goal_mult=2.0, maxHands=30000, M=5000, seed=0,
                   wong=False, record_traj=0):
    """Run M independent trips. A trip ends on ruin (bankroll <= ruin_frac*B0),
    on reaching the goal (goal_mult*B0), or after maxHands."""
    rng = np.random.default_rng(seed)
    tc_s = calib["tc"]
    rpu_s = calib["rpu"]
    edge_arr = calib["edge_arr"]
    var_unit = calib["var_unit"]
    n = len(rpu_s)

    bankroll = np.full(M, float(B0))
    alive = np.ones(M, dtype=bool)
    ruined = np.zeros(M, dtype=bool)
    reached = np.zeros(M, dtype=bool)
    peak = np.full(M, float(B0))
    maxdd = np.zeros(M)
    ruin_level = max(ruin_frac * B0, table_min)
    goal = goal_mult * B0 if goal_mult else None
    floor_bet = 0.0 if wong else table_min

    traj = None
    if (record_traj):
        traj = np.empty((record_traj, maxHands + 1))
        traj[:, 0] = B0

    steps = 0
    for t in range(maxHands):
        if (not alive.any()):
            break
        steps = t + 1
        idx = rng.integers(0, n, M)
        tc = tc_s[idx]
        rpu = rpu_s[idx]
        e = _edge_of(tc, edge_arr)
        bet = kellyFrac * (e / var_unit) * bankroll
        bet = np.where(e > 0, bet, floor_bet)
        bet = np.clip(bet, floor_bet, table_max)
        bet = np.minimum(bet, bankroll)
        bankroll = bankroll + np.where(alive, bet * rpu, 0.0)
        peak = np.maximum(peak, bankroll)
        dd = np.where(peak > 0, (peak - bankroll) / peak, 0.0)
        maxdd = np.maximum(maxdd, np.where(alive, dd, 0.0))
        nr = alive & (bankroll <= ruin_level)
        ruined |= nr
        alive = alive & ~nr
        if (goal is not None):
            ng = alive & (bankroll >= goal)
            reached |= ng
            alive = alive & ~ng
        if (traj is not None):
            traj[:, t + 1] = bankroll[:record_traj]

    if (traj is not None):
        traj = traj[:, :steps + 1]
    return {
        "ror": float(ruined.mean()),
        "p_goal": float(reached.mean()),
        "median_growth": float(np.median(bankroll) / B0),
        "mean_growth": float(bankroll.mean() / B0),
        "median_maxdd": float(np.median(maxdd)),
        "final": bankroll,
        "traj": traj,
    }


def risk_curve(calib, fractions, **kw):
    """Sweep Kelly fraction; return (frac, ror, median_growth, p_goal, median_maxdd)."""
    rows = []
    for f in fractions:
        r = simulate_trips(calib, kellyFrac=f, **kw)
        rows.append((f, r["ror"], r["median_growth"], r["p_goal"], r["median_maxdd"]))
    return rows
