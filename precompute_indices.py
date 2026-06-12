"""Engine-derived index plays: the Illustrious-18 thresholds for OUR exact game.

The textbook Illustrious-18 indices were computed decades ago for different rules
(often S17, single deck). This derives each play's index from this engine instead:
sample remaining-shoe compositions across all depths, compute the EXACT EV of the
deviation action and of basic's action with the ca.py solver, and regress the EV
gap on the Hi-Lo true count. The gap is nearly linear in the count (the premise of
index play), so the regression's zero crossing IS the index: the true count where
the deviation becomes correct in this rule set.

Run:  python precompute_indices.py
Then paste the printed ENGINE_INDICES dict into strategy.py (COUNTX plays it).
Also writes figures/engine_indices.{png,svg} comparing textbook vs engine values.
"""

import numpy as np
import ca

_HILO = np.array([0, -1, 1, 1, 1, 1, 1, 0, 0, 0, -1], float)   # index 1..10

# (label, kind, cell, textbook index). kind defines the EV gap regressed:
#   stand:  EV(stand) - EV(hit)    -> stand at tc >= idx (basic hits)
#   hit:    EV(stand) - EV(hit)    -> hit  at tc <  idx (basic stands)
#   double: EV(double) - EV(hit)   -> double at tc >= idx (basic hits)
#   split:  EV(split TT) - EV(stand 20) -> split at tc >= idx (basic stands)
#   insurance: EV(insurance bet)   -> take at tc >= idx
I18_CELLS = [
    ("insurance", "insurance", None, 3.0),
    ("16 v T", "stand", (16, 10), 0.0),
    ("15 v T", "stand", (15, 10), 4.0),
    ("T,T v 5", "split", (10, 5), 5.0),
    ("T,T v 6", "split", (10, 6), 4.0),
    ("10 v T", "double", (10, 10), 4.0),
    ("12 v 3", "stand", (12, 3), 2.0),
    ("12 v 2", "stand", (12, 2), 3.0),
    ("11 v A", "double", (11, 1), 1.0),
    ("9 v 2", "double", (9, 2), 1.0),
    ("10 v A", "double", (10, 1), 4.0),
    ("9 v 7", "double", (9, 7), 3.0),
    ("16 v 9", "stand", (16, 9), 5.0),
    ("13 v 2", "hit", (13, 2), -1.0),
    ("12 v 4", "hit", (12, 4), 0.0),
    ("12 v 5", "hit", (12, 5), -2.0),
    ("12 v 6", "hit", (12, 6), -1.0),
    ("13 v 3", "hit", (13, 3), -2.0),
]


def _dealer_after(total, soft, p, h17):
    """Dealer final-total distribution from an arbitrary started hand (same
    recursion as ca.dealer_dist, needed to start from a two-card state)."""
    memo = {}

    def rec(t, s):
        key = (t, s)
        if (key in memo):
            return memo[key]
        if (t > 21):
            res = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
        elif (t >= 18 or (t == 17 and not (s and h17))):
            a = [0.0] * 6
            a[t - 17] = 1.0
            res = tuple(a)
        else:
            a = [0.0] * 6
            for r in range(1, 11):
                if (p[r] > 0.0):
                    nt, ns = ca.add_card(t, s, r)
                    sub = rec(nt, ns)
                    for i in range(6):
                        a[i] += p[r] * sub[i]
            res = tuple(a)
        memo[key] = res
        return res

    return rec(total, soft)


def dealer_dist_peek(up, p, h17):
    """Dealer distribution conditioned on NO blackjack (the dealer peeks: if the
    hole card completes a natural, the hand is settled before the player acts).
    Only upcards T and A can hide a natural; other upcards are unconditional."""
    if (up == 10):
        ban = 1
    elif (up == 1):
        ban = 10
    else:
        return ca.dealer_dist(up, p, h17)
    start = (11, True) if up == 1 else (10, False)
    keep = 1.0 - p[ban]
    if (keep <= 0.0):
        return ca.dealer_dist(up, p, h17)
    out = [0.0] * 6
    for r in range(1, 11):
        if (r == ban or p[r] <= 0.0):
            continue
        nt, ns = ca.add_card(start[0], start[1], r)
        sub = _dealer_after(nt, ns, p, h17)
        w = p[r] / keep
        for i in range(6):
            out[i] += w * sub[i]
    return tuple(out)


def _hand_evs(total, p, dout, up):
    """Exact (stand, hit, double) EVs for a hard total under composition p."""
    es = ca.stand_ev(total, dout)
    memo = {}
    eh = 0.0
    ed = 0.0
    for r in range(1, 11):
        pr = p[r]
        if (pr > 0.0):
            nt, ns = ca.add_card(total, False, r)
            eh += pr * (ca.node_value(nt, ns, False, p, dout, up, "optimal", 0.0, memo)
                        if nt <= 21 else -1.0)
            ed += pr * 2.0 * (-1.0 if nt > 21 else ca.stand_ev(nt, dout))
    return es, eh, ed


def _split_tens_ev(p, dout, up):
    """EV of splitting T,T: two hands that each start from a ten, draw, then play
    optimally (double after split allowed). Resplits ignored (rare for tens)."""
    memo = {}
    ev1 = 0.0
    for r in range(1, 11):
        pr = p[r]
        if (pr > 0.0):
            nt, ns = ca.hand_value([10, r])
            ev1 += pr * ca.node_value(nt, ns, True, p, dout, up, "optimal", 0.0, memo)
    return 2.0 * ev1


def collect(numPacks=6, h17=True, n_samples=40000, seed=5):
    """Per cell: paired (true count, EV gap) samples across random shoe depths."""
    rng = np.random.default_rng(seed)
    deck = []
    for r in range(1, 10):
        deck += [r] * (numPacks * 4)
    deck += [10] * (numPacks * 16)
    deck = np.array(deck)
    n = len(deck)
    cut = int(n * 0.75)

    ups = sorted({c[1] for _l, _k, c, _t in I18_CELLS if c is not None} | {1})
    out = {lab: ([], []) for lab, _k, _c, _t in I18_CELLS}
    for _i in range(n_samples):
        rng.shuffle(deck)
        rmv = int(rng.integers(0, cut))
        comp = np.bincount(deck[rmv:], minlength=11).astype(float)
        N = comp.sum()
        if (N < 26):
            continue
        p = comp / N
        tc = float((_HILO * (np.bincount(deck[:rmv], minlength=11) if rmv else np.zeros(11))).sum()) / (N / 52.0)
        douts = {up: dealer_dist_peek(up, p, h17) for up in ups}
        evcache = {}
        for lab, kind, cell, _tb in I18_CELLS:
            if (kind == "insurance"):
                gap = 3.0 * p[10] - 1.0
            elif (kind == "split"):
                _t, up = cell
                gap = _split_tens_ev(p, douts[up], up) - ca.stand_ev(20, douts[up])
            else:
                total, up = cell
                key = (total, up)
                if (key not in evcache):
                    evcache[key] = _hand_evs(total, p, douts[up], up)
                es, eh, ed = evcache[key]
                gap = (ed - eh) if kind == "double" else (es - eh)
            xs, ys = out[lab]
            xs.append(tc)
            ys.append(gap)
    return out


def derive(samples, tc_window=6.0):
    """index = zero crossing of the linear fit gap ~ a + b*tc (|tc| <= window)."""
    rows = []
    for lab, kind, cell, tb in I18_CELLS:
        tc = np.asarray(samples[lab][0], float)
        gap = np.asarray(samples[lab][1], float)
        m = np.abs(tc) <= tc_window
        tc, gap = tc[m], gap[m]
        b, a = np.polyfit(tc, gap, 1)
        idx = -a / b
        rows.append((lab, kind, cell, tb, idx, b, len(tc)))
    return rows


def main(numPacks=6, n_samples=40000):
    print("Deriving engine indices: %d decks, H17, no surrender, %d samples ..."
          % (numPacks, n_samples), flush=True)
    samples = collect(numPacks=numPacks, n_samples=n_samples)
    rows = derive(samples)

    print("\n%-10s %-9s  %9s  %9s  %s" % ("play", "kind", "textbook", "engine", "slope/n"))
    for lab, kind, cell, tb, idx, b, n in rows:
        print("%-10s %-9s  %9.1f  %9.2f  (%.5f / %d)" % (lab, kind, tb, idx, b, n))

    print("\n# Paste into strategy.py:")
    bykind = {"stand": {}, "hit": {}, "double": {}, "split10": {}, "insurance": None}
    for lab, kind, cell, _tb, idx, _b, _n in rows:
        if (kind == "insurance"):
            bykind["insurance"] = round(idx, 2)
        elif (kind == "split"):
            bykind["split10"][cell[1]] = round(idx, 2)
        else:
            bykind[kind][cell] = round(idx, 2)
    print("ENGINE_INDICES = {")
    for k in ("stand", "hit", "double", "split10"):
        body = ", ".join("%s: %.2f" % (c, v) for c, v in bykind[k].items())
        print('    "%s": {%s},' % (k, body))
    print('    "insurance": %.2f,' % bykind["insurance"])
    print("}")

    # Dumbbell figure: textbook vs engine index per play.
    import matplotlib
    matplotlib.use("Agg")
    import analysis as A
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    labs = [r[0] for r in rows]
    tbs = [r[3] for r in rows]
    idxs = [r[4] for r in rows]
    y = np.arange(len(rows))[::-1]
    fig = A._new_figure(figsize=(8.2, 7.2))
    ax = fig.add_subplot(111)
    for yi, t, e in zip(y, tbs, idxs):
        ax.plot([t, e], [yi, yi], color="0.75", lw=1.4, zorder=1)
    ax.scatter(tbs, y, s=55, color="#7f8c8d", label="textbook Illustrious 18", zorder=2)
    ax.scatter(idxs, y, s=55, color="#2980b9", label="engine-derived (this game)", zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=10)
    ax.axvline(0, color="0.6", lw=0.8)
    A._style(ax, "Index plays: textbook thresholds vs engine-derived (6 decks, H17)",
             "Hi-Lo true count index (deviate at/above; hit plays deviate below)", None)
    ax.legend(fontsize=10, loc="lower right")
    FigureCanvasAgg(fig)
    fig.savefig("figures/engine_indices.png", dpi=160, bbox_inches="tight")
    fig.savefig("figures/engine_indices.svg", bbox_inches="tight")
    print("\nwrote figures/engine_indices.{png,svg}")
    return rows


if __name__ == "__main__":
    main()
