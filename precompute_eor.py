"""Precompute the effect-of-removal betting weights for OUR engine, per rule set.

ORACLE's "optimal linear" bet count must use weights derived from the actual game
it plays -- generic textbook EoR values are calibrated to a different game and
slightly underperform here. We derive the weights empirically: flat-bet basic
strategy over millions of rounds, then regress the realized per-hand edge on the
remaining-shoe composition. The regression coefficients ARE the best linear
predictor of edge, i.e. the optimal linear betting count for that rule set.

Weights are (a) balanced -- frequency-weighted mean zero, like Hi-Lo -- so the
running count is depth-neutral, and (b) normalized to Hi-Lo's per-card RMS so the
EoR true count lands on the same scale as the Hi-Lo true count (the shared bet
ramp then treats both counts identically).

Run:  python precompute_eor.py
Then paste the printed EOR_WEIGHTS dict into deck.py.
"""

import numpy as np
from blackjack import Blackjack
from config import Config

P0 = np.array([1 / 13.] * 9 + [4 / 13.])          # full-deck rank proportions (A..9 then T)
FREQ = np.array([4.] * 9 + [16.])                 # cards per rank per deck
HILO = np.array([-1, 1, 1, 1, 1, 1, 0, 0, 0, -1], float)
ROUNDS = 2500000


def collect(h17, surr, rounds, seed, NP=6):
    full = np.array([0] + [4 * NP] * 9 + [16 * NP], float)
    cfg = Config(experiment="game", strategies=("BASIC",), rounds=rounds, seed=seed,
                 shuffle="random", hitSoft17=h17, surrender=surr, numPacks=NP)
    bj = Blackjack(cfg, record=True)
    cap = {"r": -1, "rem": [], "dk": []}
    orig = bj.deck.getTrueCount
    def patched():
        v = orig()
        if (bj.numRound != cap["r"]):               # capture composition once per round
            cap["r"] = bj.numRound
            c = np.bincount(np.asarray(bj.deck.cards, dtype=int), minlength=11).astype(float)
            cap["rem"].append(c[1:11]); cap["dk"].append(bj.deck.decksRemaining())
        return v
    bj.deck.getTrueCount = patched
    for _ in range(rounds):
        bj.run()
    rec = bj.records
    res = np.array(rec["result"], float); wag = np.array(rec["wagered"], float)
    rem = np.array(cap["rem"]); dk = np.array(cap["dk"])
    n = min(len(res), len(rem)); res, wag, rem, dk = res[:n], wag[:n], rem[:n], dk[:n]
    keep = (wag > 0) & (dk > 0.4)
    return (full[1:11] - rem)[keep], dk[keep], (res / wag)[keep]


def fit(removed, dk, y, lam=5e-3):
    excess = (removed - removed.sum(1, keepdims=True) * P0) / dk[:, None]
    A = np.column_stack([np.ones(len(y)), excess])
    reg = np.eye(A.shape[1]) * lam
    reg[0, 0] = 0.0
    w = np.linalg.solve(A.T @ A + reg, A.T @ y)[1:]
    w = w - (w * P0).sum()                          # balance (freq-weighted mean -> 0)
    return w / np.sqrt((FREQ * w * w).sum() / 52.0)  # normalize to Hi-Lo per-card RMS


def bc(removed, dk, y, tag):
    return np.corrcoef((removed * tag).sum(1) / dk, y)[0, 1]


def betting_ceiling(rounds=1200000, h17=True, surr=False, seed=3):
    """How much can a NONLINEAR betting count beat the best LINEAR one (ORACLE)?
    Fit linear vs full-quadratic predictors of the realized flat-bet edge from the
    remaining composition, and compare their out-of-sample correlation with the
    edge. A tiny (or negative) nonlinear gain means ORACLE is essentially at the
    betting ceiling -- the betting edge is nearly linear in composition. Single-hand
    edge is mostly noise, so the correlations are small; the gap is the signal.

    Run:  python -c "import precompute_eor; precompute_eor.betting_ceiling()" """
    removed, dk, y = collect(h17, surr, rounds, seed)
    excess = (removed - removed.sum(1, keepdims=True) * P0) / dk[:, None]   # (n, 10)
    n = len(y)
    m = n // 2

    def fit_predict(Xtr, ytr, Xte, lam):
        A = np.column_stack([np.ones(len(ytr)), Xtr])
        reg = np.eye(A.shape[1]) * lam
        reg[0, 0] = 0.0
        beta = np.linalg.solve(A.T @ A + reg, A.T @ ytr)
        return np.column_stack([np.ones(len(Xte)), Xte]) @ beta

    def quad(X):
        cols = [X]
        for i in range(X.shape[1]):
            cols.append(X[:, i:] * X[:, i:i + 1])      # square + cross terms with j >= i
        return np.hstack(cols)

    Xq = quad(excess)
    tr, te = slice(0, m), slice(m, n)
    pl = fit_predict(excess[tr], y[tr], excess[te], 1e-2)
    pq = fit_predict(Xq[tr], y[tr], Xq[te], 1e-1)
    hic = (removed * HILO).sum(1) / dk
    cl = np.corrcoef(pl, y[te])[0, 1]
    cq = np.corrcoef(pq, y[te])[0, 1]
    ch = np.corrcoef(hic[te], y[te])[0, 1]
    print("Out-of-sample correlation with realized flat-bet edge (n=%d):" % n)
    print("  Hi-Lo count          %.4f" % ch)
    print("  best LINEAR (ORACLE) %.4f" % cl)
    print("  best NONLINEAR       %.4f" % cq)
    print("  nonlinear vs linear  %+.1f%%  (headroom above the linear betting ceiling)"
          % (100.0 * (cq - cl) / cl))
    return {"hilo": ch, "linear": cl, "nonlinear": cq}


def main():
    out = {}
    for h17 in (True, False):
        for surr in (True, False):
            rem, dk, y = collect(h17, surr, ROUNDS, seed=7)
            w = fit(rem, dk, y)                                  # stored weights: full data
            m = len(y)
            w_tr = fit(rem[:m // 2], dk[:m // 2], y[:m // 2])    # honest out-of-sample check
            oh = bc(rem[m // 2:], dk[m // 2:], y[m // 2:], HILO)
            oe = bc(rem[m // 2:], dk[m // 2:], y[m // 2:], w_tr)
            out[(h17, surr)] = w
            print("h17=%-5s surr=%-5s  n=%d  OOS corr  Hi-Lo=%.4f  engine=%.4f"
                  % (h17, surr, m, oh, oe), flush=True)

    print("\n# Paste into deck.py (ranks A=1..9, T=10), already balanced + Hi-Lo-scaled:")
    print("EOR_WEIGHTS = {")
    for (h17, surr), w in out.items():
        body = ", ".join("%d: %+.3f" % (k + 1, w[k]) for k in range(10))
        print("    (%s, %s): {%s}," % (h17, surr, body))
    print("}")


if __name__ == "__main__":
    main()
