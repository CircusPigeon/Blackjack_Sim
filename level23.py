"""Level 2/3 counting systems: the betting-correlation vs playing-efficiency trade-off.

Hi-Lo is a level-1 count (tags +/-1, 0) tuned for BETTING -- it has a high betting
correlation (BC), the alignment of its tags with each card's effect on the edge.
Level 2/3 systems (Hi-Opt II, Zen, Omega II) use larger tags (+/-2) that align less
well with the betting effect (lower BC) but track the PLAYING value of the cards
better -- a higher playing efficiency (PE), the correlation of the count with the
per-composition gain of perfect play over basic. The trade is worth it when the
playing edge is a big share of the total, i.e. in shallow / few-deck games.

This module measures BC and PE for each system FROM OUR ENGINE:
  BC -- frequency-weighted correlation of the system's tags with the engine's
        effect-of-removal weights (eor_tags).
  PE -- correlation of the system's true count with the composition-exact
        optimal-over-basic play gain, sampled with the ca.py solver.
"""

import numpy as np
import ca
from deck import eor_tags

# Per-rank tags (rank 1 = ace, 10 = T/J/Q/K). Balanced systems (tags sum to 0 over
# a deck) so the true count is meaningful without an unbalanced offset.
SYSTEMS = {
    "Hi-Lo":     {1: -1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1},
    "Hi-Opt II": {1: 0,  2: 1, 3: 1, 4: 2, 5: 2, 6: 1, 7: 1, 8: 0, 9: 0, 10: -2},
    "Zen":       {1: -1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 1, 8: 0, 9: 0, 10: -2},
    "Omega II":  {1: 0,  2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 1, 8: 0, 9: -1, 10: -2},
}
FREQ = np.array([4.0] * 9 + [16.0])


def _wcorr(a, b):
    a, b, w = np.asarray(a, float), np.asarray(b, float), FREQ / FREQ.sum()
    ma, mb = (w * a).sum(), (w * b).sum()
    cov = (w * (a - ma) * (b - mb)).sum()
    return cov / np.sqrt((w * (a - ma) ** 2).sum() * (w * (b - mb) ** 2).sum())


def betting_correlation(tags, h17=True, surrender=False):
    """Frequency-weighted correlation of the tags with the engine's EoR weights."""
    eor = [eor_tags(h17, surrender)[c] for c in range(1, 11)]
    return _wcorr([tags[c] for c in range(1, 11)], eor)


def realized_playing_efficiency(systems, n_samples=60000, numPacks=1, h17=True, seed=0):
    """The fraction of the composition-perfect playing gain (over basic) that each
    system captures with its best count-based index plays. This is the meaningful
    'playing efficiency': for every decision cell we bin samples by the system's
    true count and, in each bin, take the action with the best average EV (the
    count's optimal index play for that bin). Captured gain / perfect gain in [0,1].

    Why not a plain correlation: the total perfect-play gain is symmetric in the
    count (large at both extremes), so corr(count, gain) ~ 0; what matters is
    getting each deviation's *direction* right, which this measures."""
    from strategy import _hardPlay, _softPlay
    from play import Play
    STAND, DOUBLE = Play.STAND.value, Play.DOUBLE.value
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
    names = list(systems)
    tagarr = {nm: np.array([systems[nm][c] for c in range(1, 11)], float) for nm in names}

    cellk, A = [], {"es": [], "eh": [], "ed": [], "basic": []}
    tcs = {nm: [] for nm in names}
    for _ in range(n_samples):
        rng.shuffle(deck)
        rmv = int(rng.integers(0, cut))
        c1, c2, up = int(deck[rmv]), int(deck[rmv + 1]), int(deck[rmv + 2])
        comp = np.bincount(deck[rmv + 3:], minlength=11).astype(float)
        N = comp.sum()
        if (N < 20):
            continue
        total, soft = ca.hand_value([c1, c2])
        if (total == 21):
            continue
        p = comp / N
        dout = ca.dealer_dist(up, p, h17)
        es = ca.stand_ev(total, dout)
        eh = 0.0
        for r in range(1, 11):
            if (p[r] > 0):
                nt, ns = ca.add_card(total, soft, r)
                eh += p[r] * (ca.node_value(nt, ns, False, p, dout, up, "optimal", 0.0, {}) if nt <= 21 else -1.0)
        ed = 0.0
        for r in range(1, 11):
            if (p[r] > 0):
                nt, ns = ca.add_card(total, soft, r)
                ed += p[r] * 2.0 * (-1.0 if nt > 21 else ca.stand_ev(nt, dout))
        ba = _softPlay(total, up, True) if soft else _hardPlay(total, up, True)
        basic = ed if ba == DOUBLE else (es if ba == STAND else eh)
        cellk.append((total, bool(soft), up))
        A["es"].append(es); A["eh"].append(eh); A["ed"].append(ed); A["basic"].append(basic)
        rem = full[1:] - comp[1:]
        for nm in names:
            tcs[nm].append(float((tagarr[nm] * rem).sum()) / (N / 52.0))

    es = np.array(A["es"]); eh = np.array(A["eh"]); ed = np.array(A["ed"]); bs = np.array(A["basic"])
    perfect = float((np.maximum.reduce([es, eh, ed]) - bs).sum())
    out = {}
    for nm in names:
        tcbin = np.floor(np.asarray(tcs[nm])).astype(int)
        groups = {}
        for i in range(len(es)):
            g = groups.setdefault((cellk[i], tcbin[i]), [0.0, 0.0, 0.0, 0.0])
            g[0] += es[i]; g[1] += eh[i]; g[2] += ed[i]; g[3] += bs[i]
        captured = sum(max(g[0], g[1], g[2]) - g[3] for g in groups.values())
        out[nm] = captured / perfect
    return out


def betting_ceiling(rounds=1200000, h17=True, surr=False, seed=3):
    """How much can a NONLINEAR betting count beat the best LINEAR one (ORACLE)?
    Fit linear vs full-quadratic predictors of the realized flat-bet edge from the
    remaining composition, and compare their out-of-sample correlation with the
    edge. A tiny nonlinear gain means ORACLE is essentially at the betting ceiling
    (the betting edge is nearly linear in composition). Single-hand edge is mostly
    noise, so the correlations are small; the gap between them is the signal."""
    import precompute_eor as pe
    removed, dk, y = pe.collect(h17, surr, rounds, seed)
    excess = (removed - removed.sum(1, keepdims=True) * pe.P0) / dk[:, None]   # (n, 10)
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
    hilo = np.array([-1, 1, 1, 1, 1, 1, 0, 0, 0, -1], float)
    hic = (removed * hilo).sum(1) / dk
    cl = np.corrcoef(pl, y[te])[0, 1]
    cq = np.corrcoef(pq, y[te])[0, 1]
    ch = np.corrcoef(hic[te], y[te])[0, 1]
    print("Out-of-sample correlation with realized flat-bet edge (n=%d):" % n)
    print("  Hi-Lo count          %.4f" % ch)
    print("  best LINEAR (ORACLE) %.4f" % cl)
    print("  best NONLINEAR       %.4f" % cq)
    print("  nonlinear vs linear  %+.1f%%  (headroom above the linear betting ceiling)"
          % (100.0 * (cq - cl) / cl))
    return {"hilo": cl, "linear": cl, "nonlinear": cq, "hilo_count": ch}


def _oracle_edge(numPacks, spread, seed, rounds):
    """Bet-weighted edge (%) of ORACLE at this deck count, with or without a spread.
    Both versions play the same (EoR betting count, Hi-Lo deviations), so the
    spread-minus-flat difference isolates the pure BETTING gain."""
    import random
    from blackjack import Blackjack
    from config import Config
    random.seed(seed)              # the deck + shuffler use the global RNG; seed for reproducibility
    kw = dict(strategies=("ORACLE",), numPacks=numPacks, rounds=rounds, seed=seed,
              shuffle="random", penetration=0.75, ramp_start=1.0)
    if (spread):
        kw.update(spread_min=1, spread_max=12, spread_slope=2.0)
    else:
        kw.update(spread_min=1, spread_max=1, spread_slope=0.0)
    bj = Blackjack(Config(**kw), record=True)
    for _ in range(rounds):
        bj.run()
    res = np.asarray(bj.records["result"], float)
    wag = np.asarray(bj.records["wagered"], float)
    return 100.0 * res.sum() / wag.sum()


def edge_crossover(decks=(1, 2, 4, 6, 8), trials=15, rounds=30000, seed0=42):
    """The two pillars of advantage play by deck count, plus the best-of-both-worlds
    player that uses them together. BETTING = the edge from optimal bet variation
    (ORACLE bet spread). PLAYING = composition-perfect play at a flat bet (CEILING).
    BOTH = a player who spreads like ORACLE *and* plays like CEILING: the playing
    gain is bet-weighted because that player bets biggest in the skewed shoes where
    perfect play deviates most, so it captures more than the flat playing ceiling."""
    import json
    import matplotlib
    matplotlib.use("Agg")
    import ca
    import analysis as A
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    def ramp(tc):
        # Same 1-12 ORACLE ramp the betting sim uses (spread_min=1, slope=2, start=1).
        if (tc < 1.0):
            return 1.0
        return float(max(1, min(int(round(1 + 2.0 * (tc - 1.0))), 12)))

    bet, betci, play, both = [], [], [], []
    print("decks  betting(ORACLE)  playing(CEILING)  both(weighted play)  BOTH=total")
    for D in decks:
        cb = ca.measure_playing_ceiling(n_samples=60000, numPacks=D, h17=True,
                                        surrender=False, seed=7, bet_ramp=ramp)
        play.append(cb["opt_over_basic_pct"])
        play_bw = cb["opt_over_basic_bw_pct"]      # perfect-play gain, bet-weighted
        gains = [_oracle_edge(D, True, seed0 + t, rounds) - _oracle_edge(D, False, seed0 + t, rounds)
                 for t in range(trials)]
        g = np.array(gains)
        bet.append(g.mean())
        betci.append(1.96 * g.std(ddof=1) / np.sqrt(len(g)))
        both.append(g.mean() + play_bw)            # total edge of the combined player
        print("%4d   %+.3f           %+.3f            %+.3f               %+.3f"
              % (D, g.mean(), cb["opt_over_basic_pct"], play_bw, both[-1]), flush=True)

    fig = A._new_figure(figsize=(8.5, 5.3))
    ax = fig.add_subplot(111)
    ax.axhline(0, color="0.5", lw=0.8)
    # BOTH's uncertainty is dominated by the betting term (the bet-weighted playing
    # gain is a low-variance solver estimate), so its CI mirrors the betting CI.
    ax.errorbar(decks, both, yerr=betci, fmt="D-", color="#1a9850", lw=2.2, markersize=7,
                capsize=4, label="BOTH  (ORACLE bets + CEILING play)")
    ax.errorbar(decks, bet, yerr=betci, fmt="o-", color="#2980b9", capsize=4,
                label="betting only  (ORACLE bet spread)")
    ax.plot(decks, play, "s--", color="#8e44ad", label="playing only  (CEILING, flat bet)")
    ax.set_xticks(list(decks))
    A._style(ax, "Best of both worlds: betting (ORACLE) + perfect play (CEILING) by deck count",
             "number of decks (penetration fixed at 75%)", "edge over flat-bet basic (% per hand)")
    ax.legend(fontsize=11)
    FigureCanvasAgg(fig)
    fig.savefig("figures/edge_crossover.png", dpi=160, bbox_inches="tight")
    fig.savefig("figures/edge_crossover.svg", bbox_inches="tight")
    data = {"decks": list(decks), "betting": bet, "betting_ci": betci,
            "playing_ceiling": play, "both": both}
    with open("figures/edge_crossover_data.json", "w") as f:
        json.dump(data, f, indent=2)
    print("wrote figures/edge_crossover.{png,svg} + edge_crossover_data.json")
    return data


def main():
    import matplotlib
    matplotlib.use("Agg")
    import analysis as A
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    # ORACLE = the engine's EoR weights themselves (the BC-optimal linear count).
    systems = dict(SYSTEMS)
    eor = eor_tags(True, False)
    systems["ORACLE (EoR)"] = {c: eor[c] for c in range(1, 11)}

    print("system        level   BC      PE (1 deck, share of perfect-play gain)")
    pe = realized_playing_efficiency(systems, n_samples=60000, numPacks=1, seed=1)
    rows = []
    for name, tags in systems.items():
        lvl = max(abs(v) for v in tags.values())
        bc = betting_correlation(tags)
        rows.append((name, bc, pe[name]))
        print("%-13s %4.0f   %.3f   %.3f" % (name, lvl, bc, pe[name]), flush=True)

    fig = A._new_figure(figsize=(8.0, 6.0))
    ax = fig.add_subplot(111)
    for name, bc, pe in rows:
        color = "#8e44ad" if "ORACLE" in name else ("#2980b9" if name == "Hi-Lo" else "#c0392b")
        ax.scatter([bc], [pe], s=70, color=color, zorder=3)
        ax.annotate(name, (bc, pe), xytext=(6, 4), textcoords="offset points", fontsize=10)
    A._style(ax, "The betting-vs-playing trade-off in counting systems",
             "betting correlation (BC)", "playing efficiency (share of perfect-play gain, 1 deck)")
    FigureCanvasAgg(fig)
    fig.savefig("figures/level23_bc_pe.png", dpi=160, bbox_inches="tight")
    fig.savefig("figures/level23_bc_pe.svg", bbox_inches="tight")
    print("wrote figures/level23_bc_pe.{png,svg}")


if __name__ == "__main__":
    main()
