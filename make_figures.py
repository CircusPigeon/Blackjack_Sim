"""Regenerate the curated figures for the write-up / website.

Each "figure spec" pins reproducible Configs (fixed seeds) and runs them through
the engine, rendering publication figures (SVG + PNG) into figures/ plus a
figures/manifest.json of the headline numbers -- so the write-up can quote one
source of truth and never drift from the images.

Every edge estimate is Monte-Carlo: a condition is run over many independent
trials (different shoes) and shown as a mean with a 95% confidence interval.
Paired comparisons (TRACK vs BASIC, ORACLE vs COUNT) are differenced per trial,
since those strategies share the same shoes within a run -- that cancels
shoe-to-shoe noise. The heat and bankroll experiments are Monte-Carlo by
construction (each point averages thousands of resampled sessions).

    python make_figures.py --list                 # list the figure specs
    python make_figures.py                         # regenerate everything
    python make_figures.py --only heat,penetration
    python make_figures.py --trials 40 --rounds 60000   # higher fidelity (slower)
    python make_figures.py --smoke                 # tiny sizes, just to test plumbing

NOTE: the lineup below is a DRAFT for review; tune conditions/seeds/sizes first.
"""

import os
import io
import sys
import math
import json
import argparse
import contextlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg

from config import Config
import experiment
import analysis as A
import heat

FIGDIR = "figures"
SMOKE = False
TRIALS_DEFAULT = 30
ROUNDS_DEFAULT = 40000

# The casino-shuffle + live-tracking spec and the many-player spec cost far more
# per hand, so they run with proportionally fewer rounds (their effects are large
# and don't need as many hands to resolve). Keeps the whole run to ~25 min.
HEAVY = {"shuffle_tracking": 0.5, "dummy_players": 0.6}

# Specs that need extra Monte-Carlo trials to read cleanly. dummy_players is
# EV-flat by design, so it needs tight, overlapping CIs to LOOK flat (not noisy).
SPEC_TRIALS = {"dummy_players": 2.5, "shuffle_tracking": 2.0}

# Realistic advantage-player bet spread used across the counting figures: a 1-to-12
# ramp climbing 2 units per true count from TC +1 (so it reaches the cap ~TC +6).
# Applied by trial_edges() unless a spec overrides a given key.
SPREAD = dict(spread_min=1, spread_max=12, ramp_start=1.0, spread_slope=2.0)


def R(big, small):
    """Pick a run size: full fidelity normally, tiny under --smoke."""
    return small if SMOKE else big


# --- engine helpers --------------------------------------------------------

def _bundle(cfg):
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        return experiment.run(cfg, outdir="results", save_plots=False) or {}


def _edge(bundle, strat):
    for (s, w, p, e) in bundle.get("summary", []):
        if (s == strat):
            return e
    return 0.0


def trial_edges(strategies, trials, rounds, seed0=42, **kw):
    """Run `trials` independent sessions (shared shoes within each run). Return
    {strategy: np.array of per-trial edge %}. Because all strategies sit at the
    same table per run, the arrays are paired across strategies."""
    cfg_kw = dict(SPREAD)
    cfg_kw.update(kw)
    out = {s: [] for s in strategies}
    for t in range(trials):
        b = _bundle(Config(experiment="game", strategies=tuple(strategies),
                           rounds=rounds, seed=seed0 + t, **cfg_kw))
        for s in strategies:
            out[s].append(_edge(b, s))
    return {s: np.asarray(v, float) for s, v in out.items()}


def mean_ci(arr):
    """Mean and 95% confidence half-width (1.96 * standard error)."""
    arr = np.asarray(arr, float)
    m = float(arr.mean())
    if (arr.size < 2):
        return m, 0.0
    return m, 1.96 * float(arr.std(ddof=1) / np.sqrt(arr.size))


# --- generic plot helpers (match the analysis.py house style) --------------

def _fig_bars(labels, values, title, ylabel, colors=None, errors=None):
    fig = A._new_figure(figsize=(8.4, 5.2))
    ax = fig.add_subplot(111)
    ax.axhline(0, color="0.5", lw=0.8)
    ax.bar(range(len(labels)), values, color=(colors or ["#2980b9"] * len(labels)),
           yerr=errors, capsize=5, ecolor="0.25")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10)
    A._style(ax, title, None, ylabel)
    return fig


def _fig_lines(x, series, title, xlabel, ylabel):
    fig = A._new_figure()
    ax = fig.add_subplot(111)
    for s in series:
        ax.plot(x, s["y"], marker="o", lw=1.7, label=s["label"])
    A._style(ax, title, xlabel, ylabel)
    ax.legend(fontsize=11)
    return fig


def _fig_line_band(x, y, ci, title, xlabel, ylabel, color="#2980b9"):
    y = np.asarray(y, float)
    ci = np.asarray(ci, float)
    fig = A._new_figure()
    ax = fig.add_subplot(111)
    ax.axhline(0, color="0.5", lw=0.8)
    ax.plot(x, y, "o-", color=color, lw=1.8)
    ax.fill_between(x, y - ci, y + ci, color=color, alpha=0.2, label="95% CI")
    A._style(ax, title, xlabel, ylabel)
    ax.legend(fontsize=11)
    return fig


def _stat(m, ci):
    return {"mean": round(m, 4), "ci95": round(ci, 4)}


# --- figure specs (DRAFT lineup) -------------------------------------------

def exp_shuffle_tracking(trials, rounds):
    """Shuffle tracking only beats a sloppy, uncut shoe; the cut neutralizes it."""
    conds = [
        ("random\n(control)", dict(shuffle="random"), "#999999"),
        ("casino\n3 riffle + cut", dict(shuffle="casino", shuffleRiffles=3, shuffleStrips=1, shuffleCut=True), "#27ae60"),
        ("casino\n3 riffle, no cut", dict(shuffle="casino", shuffleRiffles=3, shuffleStrips=1, shuffleCut=False), "#e67e22"),
        ("casino\n2 riffle, no cut", dict(shuffle="casino", shuffleRiffles=2, shuffleStrips=0, shuffleCut=False), "#c0392b"),
    ]
    means, cis, nums = [], [], {}
    for label, kw, _c in conds:
        ed = trial_edges(["BASIC", "TRACK"], trials, rounds, **kw)
        m, ci = mean_ci(ed["TRACK"] - ed["BASIC"])          # paired gain per trial
        means.append(m)
        cis.append(ci)
        nums[label.replace("\n", " ")] = _stat(m, ci)
    fig = _fig_bars([c[0] for c in conds], means,
                    "Shuffle tracking: edge gained over basic strategy",
                    "TRACK − BASIC edge  (% per hand, 95% CI)",
                    colors=[c[2] for c in conds], errors=cis)
    return [("shuffle_tracking", fig)], nums


def exp_heat(trials, rounds):
    """The detection trade-off, and how the optimal ramp depends on the spread cap.
    Heat is Monte-Carlo by construction: M resampled sessions per ramp point (M is
    this experiment's "trials" -- raise it for smoother curves)."""
    calib = experiment._calibration()
    slopes = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8]
    M = R(40000, 4000)
    maxH = R(2000, 400)
    sweeps = {cap: heat.aggressiveness_sweep(calib, slopes, threshold=2.0, warmup=25,
                                             base_rate=0.12, pivot=1.0, min_bet=1, max_bet=cap,
                                             maxHands=maxH, M=M, seed=42)
              for cap in (6, 12, 20)}
    rows = sweeps[12]                                       # main curve at the realistic 1-12 cap
    curve = A.fig_heat_curve(rows)
    best = max(rows, key=lambda r: r[3])
    series, nums = [], {"optimal_ramp": best[0], "total_at_opt": round(best[3], 2)}
    for cap in (6, 12, 20):
        series.append({"label": "spread 1–%d" % cap, "y": [r[3] for r in sweeps[cap]]})
        nums["optimal_ramp_cap_%d" % cap] = max(sweeps[cap], key=lambda r: r[3])[0]
    tradeoff = _fig_lines(slopes, series,
                          "Heat: profit per session vs ramp, by spread cap",
                          "ramp (units per true count)", "total profit per session (units)")
    return [("heat_curve", curve), ("heat_spread_tradeoff", tradeoff)], nums


def exp_bankroll(trials, rounds):
    """Risk of ruin vs growth as a function of Kelly fraction.
    (Bankroll is Monte-Carlo by construction: each point resamples thousands of trips.)"""
    b = _bundle(Config(experiment="bankroll", bankroll_horizon=R(50000, 5000), seed=42))
    fig = A.fig_risk_curve(b["risk"])
    risk = {round(r[0], 2): r for r in b["risk"]}
    nums = {"RoR_full_kelly": (round(risk[1.0][1], 3) if 1.0 in risk else None),
            "RoR_half_kelly": (round(risk[0.5][1], 3) if 0.5 in risk else None)}
    return [("bankroll_risk", fig)], nums


def exp_bankroll_paths(trials, rounds):
    """Monte-Carlo bankroll trajectories make risk-of-ruin tangible: ~120 sample
    trips at half vs full Kelly, ruined paths (hit the 50% floor) in red. Half
    Kelly grows steadily with few ruins; full Kelly swings wildly and busts often."""
    import bankroll as bk
    calib = bk.calibrate(bk.load_or_make_calibration())
    B0 = 2000.0
    maxH = R(40000, 3000)
    npath = 120
    ruin_level = 0.5 * B0
    fig = A._new_figure(figsize=(11.5, 4.8))
    axes = [fig.add_subplot(1, 2, 1), fig.add_subplot(1, 2, 2)]
    nums = {}
    for ax, frac, title in zip(axes, (0.5, 1.0), ("half Kelly", "full Kelly")):
        r = bk.simulate_trips(calib, kellyFrac=frac, B0=B0, maxHands=maxH, M=8000,
                              ruin_frac=0.5, goal_mult=0, table_max=500.0,
                              record_traj=npath, seed=1)
        traj = r["traj"]
        st = max(1, traj.shape[1] // 500)
        xs = np.arange(0, traj.shape[1], st)
        for i in range(traj.shape[0]):
            red = traj[i, -1] <= ruin_level * 1.001
            ax.plot(xs, traj[i, ::st], lw=0.5, alpha=0.55,
                    color=("#c0392b" if red else "#2980b9"))
        ax.axhline(ruin_level, color="0.35", ls=":", lw=1.2)
        ax.axhline(B0, color="0.6", lw=0.8)
        ax.set_yscale("log")
        ax.set_title("%s   (risk of ruin %.0f%%)" % (title, 100 * r["ror"]), fontsize=12)
        ax.set_xlabel("hands played", fontsize=11)
        ax.tick_params(labelsize=10)
        nums["RoR_" + title.split()[0]] = round(r["ror"], 3)
    axes[0].set_ylabel("bankroll (units, log scale)", fontsize=11)
    fig.suptitle("Bankroll trajectories: half Kelly is survivable, full Kelly courts ruin",
                 fontsize=13)
    return [("bankroll_paths", fig)], nums


def exp_ceiling(trials, rounds):
    """The PLAYING ceiling: how much composition-perfect play beats basic strategy,
    versus how little of that a Hi-Lo counter's deviations (what COUNT and ORACLE
    play) actually capture. Flat bet, by penetration -- the widening gap is edge
    that lives in perfect composition-dependent play, impractical for a human."""
    import ca
    NP, h17, surr = 6, True, True
    n_cards = NP * 52
    cut = int(n_cards * 0.75)
    nb = 6
    n_samp = R(30000, 1500)
    xs, perf, perf_ci, dev, dev_ci = [], [], [], [], []
    for i in range(nb):
        lo, hi = int(cut * i / nb), int(cut * (i + 1) / nb)
        b = ca.measure_playing_ceiling(n_samples=n_samp, numPacks=NP, h17=h17, surrender=surr,
                                       rem_lo=lo, rem_hi=hi, seed=100 + i)
        xs.append(100.0 * (lo + hi) / 2.0 / n_cards)
        perf.append(b["opt_over_basic_pct"]); perf_ci.append(1.96 * b["opt_over_basic_se"])
        dev.append(b["hilo_over_basic_pct"]); dev_ci.append(1.96 * b["hilo_over_basic_se"])
    fig = A._new_figure()
    ax = fig.add_subplot(111)
    ax.axhline(0, color="0.5", lw=0.8)
    ax.errorbar(xs, perf, yerr=perf_ci, fmt="o-", color="#8e44ad", capsize=3,
                label="composition-perfect play")
    ax.errorbar(xs, dev, yerr=dev_ci, fmt="s--", color="#2980b9", capsize=3,
                label="Hi-Lo deviations (COUNT / ORACLE play)")
    A._style(ax, "Playing ceiling: perfect play vs Hi-Lo deviations, by penetration (flat bet)",
             "percent of shoe dealt", "edge gained over basic strategy (% per hand)")
    ax.legend(fontsize=11)
    nums = {"by_pct_dealt": {int(round(x)): {"perfect": round(p, 4), "hilo_dev": round(d, 4)}
                            for x, p, d in zip(xs, perf, dev)}}
    return [("ceiling", fig)], nums


def exp_oracle_vs_count(trials, rounds):
    """Hi-Lo and the effect-of-removal "optimal" linear count sort hands by edge
    essentially identically -> Hi-Lo is already at the linear betting ceiling.

    Measured flat-bet (BASIC): for every round we capture BOTH the Hi-Lo true
    count and the EoR true count, then bucket the realized per-hand edge by each.
    The two edge-vs-count curves overlap and the betting correlations match, so
    the EoR-optimal weights add nothing the simple integer count doesn't already
    capture. (A bet-ramp comparison is the wrong tool here: equal counts fed an
    identical ramp differ only by betting-calibration noise, not information.)"""
    from blackjack import Blackjack
    lo, hi = -4, 6
    # per count, per bucket: [n, sum_rpu, sumsq_rpu, sum_result, sum_wagered]
    accH = {b: [0, 0.0, 0.0, 0.0, 0.0] for b in range(lo, hi + 1)}
    accE = {b: [0, 0.0, 0.0, 0.0, 0.0] for b in range(lo, hi + 1)}
    S = dict.fromkeys(("n", "h", "e", "y", "hh", "ee", "yy", "hy", "ey"), 0.0)

    for t in range(trials):
        bj = Blackjack(Config(experiment="game", strategies=("BASIC",),
                              rounds=rounds, seed=42 + t, shuffle="random"), record=True)
        cap = {"r": -1, "eor": []}
        orig = bj.deck.getTrueCount
        def patched(orig=orig, bj=bj, cap=cap):
            v = orig()
            if (bj.numRound != cap["r"]):       # capture EoR once per round, aligned with the record
                cap["r"] = bj.numRound
                cap["eor"].append(bj.deck.getEorTrueCount())
            return v
        bj.deck.getTrueCount = patched
        for _ in range(rounds):
            bj.run()
        rec = bj.records
        h = np.asarray(rec["true_count"], float)
        res = np.asarray(rec["result"], float)
        wag = np.asarray(rec["wagered"], float)
        e = np.asarray(cap["eor"], float)
        m = min(len(h), len(e))
        h, res, wag, e = h[:m], res[:m], wag[:m], e[:m]
        keep = wag > 0
        h, res, wag, e = h[keep], res[keep], wag[keep], e[keep]
        rpu = res / wag
        S["n"] += len(rpu); S["y"] += rpu.sum(); S["yy"] += (rpu * rpu).sum()
        S["h"] += h.sum(); S["hh"] += (h * h).sum(); S["hy"] += (h * rpu).sum()
        S["e"] += e.sum(); S["ee"] += (e * e).sum(); S["ey"] += (e * rpu).sum()
        for arr, acc in ((h, accH), (e, accE)):
            bk = np.clip(np.floor(arr).astype(int), lo, hi)
            for b in range(lo, hi + 1):
                msk = bk == b
                nb = int(msk.sum())
                if (nb):
                    r = rpu[msk]
                    acc[b][0] += nb; acc[b][1] += r.sum(); acc[b][2] += (r * r).sum()
                    acc[b][3] += res[msk].sum(); acc[b][4] += wag[msk].sum()

    def corr(sx, sxx, sxy):
        n = S["n"]
        cov = sxy - sx * S["y"] / n
        vx = sxx - sx * sx / n
        vy = S["yy"] - S["y"] * S["y"] / n
        return cov / math.sqrt(vx * vy)
    bcH, bcE = corr(S["h"], S["hh"], S["hy"]), corr(S["e"], S["ee"], S["ey"])

    xs = list(range(lo, hi + 1))
    def curve(acc):
        ys, es = [], []
        for b in xs:
            n, sr, sq, sres, swag = acc[b]
            if (n > 1 and swag > 0):
                ys.append(100.0 * sres / swag)
                es.append(1.96 * 100.0 * math.sqrt(max(sq / n - (sr / n) ** 2, 0.0) / n))
            else:
                ys.append(float("nan")); es.append(0.0)
        return ys, es
    yH, eH = curve(accH)
    yE, eE = curve(accE)

    fig = A._new_figure()
    ax = fig.add_subplot(111)
    ax.axhline(0, color="0.5", lw=0.8)
    ax.errorbar(xs, yH, yerr=eH, fmt="o-", color="#2980b9", capsize=3,
                label="Hi-Lo count  (betting corr %.3f)" % bcH)
    ax.errorbar(xs, yE, yerr=eE, fmt="s--", color="#8e44ad", capsize=3,
                label="EoR-optimal count  (betting corr %.3f)" % bcE)
    A._style(ax, "Two betting counts sort edge identically: Hi-Lo is at the linear ceiling",
             "true count (bucket)", "flat-bet edge per hand (%)")
    ax.legend(fontsize=11)
    nums = {"betting_corr_hilo": round(bcH, 4), "betting_corr_eor": round(bcE, 4),
            "note": "near-identical betting correlation -> the EoR-optimal weights add "
                    "nothing over plain Hi-Lo (Hi-Lo is at the linear betting ceiling)"}
    return [("oracle_vs_count", fig)], nums


def exp_linear_counts(trials, rounds):
    """The three linear betting counts side by side. Hi-Lo is a coarse integer
    rounding of the (nearly identical) effect-of-removal weights -- Griffin's
    textbook generic-game values and the ones derived from our own H17+surrender
    game. Same shape -> all three sort hands by edge equally well (oracle_vs_count)."""
    from deck import eor_tags, _EOR_BASE
    freq = np.array([4.0] * 9 + [16.0])

    def norm(v):
        v = np.asarray(v, float)
        return v / np.sqrt((freq * v * v).sum() / 52.0)      # scale to Hi-Lo per-card RMS

    ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T"]
    hilo = norm([-1, 1, 1, 1, 1, 1, 0, 0, 0, -1])
    griffin = norm([_EOR_BASE[c] for c in range(1, 11)])
    w = eor_tags(True, True)
    engine = norm([w[c] for c in range(1, 11)])
    fig = A._new_figure(figsize=(9.2, 5.0))
    ax = fig.add_subplot(111)
    x = np.arange(10)
    bw = 0.27
    ax.axhline(0, color="0.5", lw=0.8)
    ax.bar(x - bw, hilo, bw, label="Hi-Lo", color="#2980b9")
    ax.bar(x, griffin, bw, label="Griffin (textbook, generic game)", color="#95a5a6")
    ax.bar(x + bw, engine, bw, label="EoR-optimal (our H17 + surrender game)", color="#8e44ad")
    ax.set_xticks(x)
    ax.set_xticklabels(ranks)
    A._style(ax, "Linear betting counts: Hi-Lo is a coarse rounding of the optimal weights",
             "card rank", "tag value (scaled to Hi-Lo RMS)")
    ax.legend(fontsize=10)
    nums = {r: {"hilo": round(h, 2), "griffin": round(g, 2), "engine": round(e, 2)}
            for r, h, g, e in zip(ranks, hilo, griffin, engine)}
    return [("linear_counts", fig)], nums


def exp_dummy_players(trials, rounds):
    """More players don't change per-hand EV; they cut hands/hour (the card-eater myth)."""
    counts = [0, 1, 2, 4, 6]
    means, cis, rates = [], [], []
    for d in counts:
        ed = trial_edges(["COUNT"], trials, rounds, shuffle="random", dummyPlayers=d)
        m, ci = mean_ci(ed["COUNT"])
        means.append(m)
        cis.append(ci)
        rates.append(A.rounds_per_hour(d + 1))
    fig = A._new_figure()
    ax1 = fig.add_subplot(111)
    eb = ax1.errorbar(counts, means, yerr=cis, fmt="o-", color="#2980b9", capsize=5)
    ax1.set_ylim(min(np.array(means) - np.array(cis)) - 0.3,
                 max(np.array(means) + np.array(cis)) + 0.3)
    A._style(ax1, "More players: same edge, fewer hands/hour",
             "number of other players at the table", "COUNT edge per hand (%)")
    ax2 = ax1.twinx()
    hh, = ax2.plot(counts, rates, "s--", color="#c0392b")
    ax2.set_ylabel("rounds dealt per hour", fontsize=12)
    ax1.legend([eb, hh], ["COUNT edge (%, 95% CI)", "hands / hour"],
               loc="center right", fontsize=11)
    nums = {"edge_by_players": {d: _stat(m, ci) for d, m, ci in zip(counts, means, cis)},
            "hands_per_hour": {d: round(r, 0) for d, r in zip(counts, rates)}}
    return [("dummy_players", fig)], nums


def exp_penetration(trials, rounds):
    """A counter's edge rises the deeper the dealer deals before reshuffling."""
    pens = [0.50, 0.65, 0.75, 0.85, 0.90]
    means, cis, nums = [], [], {}
    for p in pens:
        ed = trial_edges(["COUNT"], trials, rounds, shuffle="random", penetration=p)
        m, ci = mean_ci(ed["COUNT"])
        means.append(m)
        cis.append(ci)
        nums["%.2f" % p] = _stat(m, ci)
    fig = _fig_line_band(pens, means, cis,
                         "Counter edge rises with deck penetration",
                         "penetration (fraction of shoe dealt before reshuffle)",
                         "COUNT edge per hand (%)")
    return [("penetration_sweep", fig)], nums


def exp_kills_counting(trials, rounds):
    """6:5 payouts, a CSM, and shallow penetration each neutralize card counting."""
    base = dict(shuffle="random", numPacks=6, penetration=0.75, blackjackPays=1.5, hitSoft17=True)
    conds = [
        ("baseline\n6D 3:2 75%", {}, "#27ae60"),
        ("6:5 payout", dict(blackjackPays=1.2), "#c0392b"),
        ("continuous\nshuffler", dict(shuffle="csm"), "#c0392b"),
        ("shallow pen\n50%", dict(penetration=0.50), "#e67e22"),
    ]
    means, cis, nums = [], [], {}
    for label, over, _c in conds:
        kw = dict(base)
        kw.update(over)
        ed = trial_edges(["COUNT"], trials, rounds, **kw)
        m, ci = mean_ci(ed["COUNT"])
        means.append(m)
        cis.append(ci)
        nums[label.replace("\n", " ")] = _stat(m, ci)
    fig = _fig_bars([c[0] for c in conds], means, "What kills card counting",
                    "COUNT edge per hand  (%, 95% CI)",
                    colors=[c[2] for c in conds], errors=cis)
    return [("kills_counting", fig)], nums


# Ordered cheap-first so the quick figures land early and a long run's slow tail
# (dummy_players, shuffle_tracking) comes last.
FIGURES = {
    "bankroll": (exp_bankroll, "Risk of ruin vs Kelly fraction"),
    "bankroll_paths": (exp_bankroll_paths, "Bankroll trajectories: half vs full Kelly"),
    "heat": (exp_heat, "Detection trade-off + optimal ramp vs spread cap"),
    "oracle_vs_count": (exp_oracle_vs_count, "Hi-Lo sits at the linear betting ceiling"),
    "linear_counts": (exp_linear_counts, "Hi-Lo vs Griffin vs engine-EoR weights"),
    "ceiling": (exp_ceiling, "Playing ceiling: perfect play vs Hi-Lo deviations"),
    "penetration": (exp_penetration, "Counter edge rises with penetration"),
    "kills_counting": (exp_kills_counting, "6:5 / CSM / shallow pen neutralize counting"),
    "dummy_players": (exp_dummy_players, "Same edge, fewer hands/hour"),
    "shuffle_tracking": (exp_shuffle_tracking, "Tracking only beats a sloppy, uncut shoe"),
}


# --- runner ----------------------------------------------------------------

def _keep_awake():
    """Stop the machine from sleeping while a long run is in progress (Windows).
    The request is released automatically when the process exits."""
    if (sys.platform == "win32"):
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        except Exception:
            pass


def save_fig(fig, base):
    FigureCanvasAgg(fig)
    paths = []
    for ext in ("svg", "png"):
        p = os.path.join(FIGDIR, base + "." + ext)
        fig.savefig(p, dpi=160, bbox_inches="tight")
        paths.append(p)
    return paths


def main():
    global SMOKE
    ap = argparse.ArgumentParser(description="Regenerate write-up / website figures.")
    ap.add_argument("--only", help="comma-separated subset of figure specs")
    ap.add_argument("--list", action="store_true", help="list specs and exit")
    ap.add_argument("--smoke", action="store_true", help="tiny sizes (pipeline test)")
    ap.add_argument("--trials", type=int, default=TRIALS_DEFAULT, help="Monte-Carlo trials per condition")
    ap.add_argument("--rounds", type=int, default=ROUNDS_DEFAULT, help="hands per trial")
    args = ap.parse_args()

    if (args.list):
        for name, (_fn, desc) in FIGURES.items():
            print("  %-18s %s" % (name, desc))
        return

    SMOKE = args.smoke
    _keep_awake()
    trials = R(args.trials, 4)
    rounds = R(args.rounds, 800)
    names = (args.only.split(",") if args.only else list(FIGURES))
    os.makedirs(FIGDIR, exist_ok=True)
    manifest_path = os.path.join(FIGDIR, "manifest.json")

    # Resume-friendly: merge into any existing manifest and save after EACH spec,
    # so a long run that gets interrupted keeps its completed figures and can be
    # finished later with --only <missing specs>.
    manifest = {}
    if (os.path.exists(manifest_path)):
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    print("Monte-Carlo: %d trials x %d hands per condition%s"
          % (trials, rounds, "  (SMOKE)" if SMOKE else ""))
    import time
    for name in names:
        if (name not in FIGURES):
            print("skip unknown spec: %s" % name)
            continue
        fn, desc = FIGURES[name]
        r = rounds if SMOKE else max(2000, int(rounds * HEAVY.get(name, 1.0)))
        tr = trials if SMOKE else max(2, int(round(trials * SPEC_TRIALS.get(name, 1.0))))
        t0 = time.time()
        print("[%s] %s  (%d x %d) ..." % (name, desc, tr, r), flush=True)
        figs, nums = fn(tr, r)
        files = []
        for base, fig in figs:
            files += save_fig(fig, base)
            print("    wrote " + base + ".{svg,png}", flush=True)
        manifest[name] = {"description": desc, "numbers": nums, "files": files,
                          "trials": tr, "rounds": r, "smoke": SMOKE}
        manifest["_meta"] = {"spread": SPREAD, "trials": trials, "rounds": rounds, "smoke": SMOKE,
                             "note": "spread applies to the counting figures"}
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print("    done in %.0fs, manifest saved" % (time.time() - t0), flush=True)
    print("manifest -> " + manifest_path)


if __name__ == "__main__":
    main()
