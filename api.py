"""Headless, JSON-in / JSON-out entry point to the lab.

This is the single seam between the simulation engine and any front-end. The
desktop GUI renders matplotlib figures; but a web page, a CLI, a small Flask /
FastAPI backend, or an in-browser Pyodide build all want plain data. They call
run_config(params) and get back a JSON-serializable dict:

    {
      "ok": bool,
      "experiment": "game" | "heat" | "bankroll" | "ceiling",
      "config": {...},          # the (clamped) config actually run
      "log": "....",            # the formatted text tables, for a <pre> fallback
      "plots": [ {id,title,type,...series...}, ... ],   # ready for any chart lib
      "tables": [ {title, columns, rows}, ... ],
      "error": str | None,
    }

No matplotlib, no printing to the real stdout, no file writes: just data. Run it
as a CLI to see exactly what a web client would receive:

    python api.py '{"experiment":"game","rounds":4000,"strategies":["BASIC","COUNT"]}'
"""

import io
import json
import sys
import contextlib

from config import Config
from analysis import _drop_sparse

# Config fields a client is allowed to set. Anything else in the request is
# ignored, so a Config(**params) can never be tripped up by junk or used to
# reach internals. (Whitelist, not blacklist, on purpose.)
PUBLIC_FIELDS = {
    "experiment", "label", "seed", "rounds", "trials",
    "numPacks", "penetration", "hitSoft17", "blackjackPays", "surrender",
    "strategies", "spread_min", "spread_max", "ramp_start",
    "shuffle", "shuffleRiffles", "shuffleStrips", "shuffleCut",
    "dummyPlayers", "dummyStrategy",
    "heat_threshold", "heat_warmup", "heat_rate", "heat_maxHands",
    "bankroll_units", "ruin_frac", "bankroll_horizon",
    "heat_live", "bankroll_live", "kelly_fraction", "ceiling_samples",
}

# Bound the work a single request can ask for. A public endpoint must cap this
# or one caller can run 10^9 hands and tie up the server. We clamp (not reject)
# so a request always returns something; the clamped config is echoed back.
LIMITS = {
    "rounds": (1, 200000),
    "trials": (1, 2000),
    "ceiling_samples": (1000, 200000),
    "heat_maxHands": (100, 5000),
    "bankroll_horizon": (1000, 200000),
    "numPacks": (1, 8),
    "dummyPlayers": (0, 6),
    "penetration": (0.30, 0.95),
    "spread_min": (1, 50),
    "spread_max": (1, 200),
}


def _clamp(name, value):
    lo, hi = LIMITS[name]
    try:
        v = type(lo)(value)
    except (TypeError, ValueError):
        return value
    return max(lo, min(hi, v))


def make_config(params):
    """Build a Config from an untrusted dict: whitelist the keys, clamp the
    expensive ones, coerce strategies to a tuple."""
    clean = {k: v for k, v in (params or {}).items() if k in PUBLIC_FIELDS}
    for name in LIMITS:
        if (name in clean):
            clean[name] = _clamp(name, clean[name])
    if ("strategies" in clean and clean["strategies"] is not None):
        clean["strategies"] = tuple(clean["strategies"]) or ("BASIC",)
    return Config(**clean)


# --- serialization helpers -------------------------------------------------

def _f(x, nd=4):
    return round(float(x), nd)


def _downsample(seq, k=200):
    """Thin a long path down to ~k points, keeping original hand indices."""
    seq = list(seq)
    n = len(seq)
    if (n <= k):
        return list(range(n)), [_f(v, 2) for v in seq]
    step = n / float(k)
    xs, ys = [], []
    for i in range(k):
        j = int(i * step)
        xs.append(j)
        ys.append(_f(seq[j], 2))
    xs.append(n - 1)
    ys.append(_f(seq[-1], 2))
    return xs, ys


def _hist(values, bins=30):
    import numpy as np
    v = np.asarray([float(x) for x in values], dtype=float)
    if (v.size == 0):
        return {"counts": [], "edges": []}
    counts, edges = np.histogram(v, bins=bins)
    return {"counts": [int(c) for c in counts],
            "edges": [_f(e, 2) for e in edges],
            "mean": _f(v.mean(), 2), "median": _f(np.median(v), 2)}


def _plots(cfg, bundle):
    plots = []
    hero = bundle.get("hero")

    er = bundle.get("edge_rows")
    if (er and hero and er.get(hero)):
        data = _drop_sparse(er[hero])
        plots.append({
            "id": "edge", "type": "bar",
            "title": "Player edge by true count  [%s]" % hero,
            "xlabel": "true count (bucket)", "ylabel": "edge %  (green = player favored)",
            "x": [int(d[0]) for d in data],
            "y": [_f(d[2]) for d in data],
            "hands": [int(d[1]) for d in data],
        })

    trajs = bundle.get("trajectories")
    rec = bundle.get("records")
    if (trajs):
        series = []
        for path in trajs[:40]:
            xs, ys = _downsample(path, 200)
            series.append({"x": xs, "y": ys})
        plots.append({
            "id": "bankroll", "type": "multiline",
            "title": "Bankroll trajectories  (hero=%s)" % hero,
            "xlabel": "hand number", "ylabel": "bankroll (units)",
            "series": series,
        })
    elif (rec):
        by = {}
        n = len(rec["round"])
        for i in range(n):
            s = rec["strategy"][i]
            d = by.setdefault(s, ([], []))
            d[0].append(rec["round"][i])
            d[1].append(rec["bankroll"][i])
        series = []
        for s, (rs, bs) in by.items():
            _, ys = _downsample(bs, 400)
            xs, _ = _downsample(rs, 400)
            series.append({"label": s, "x": xs, "y": ys})
        if (series):
            plots.append({
                "id": "bankroll", "type": "multiline",
                "title": "Bankroll over time",
                "xlabel": "hand number", "ylabel": "bankroll (units)",
                "series": series,
            })

    results = bundle.get("results")
    if (results):
        plots.append({
            "id": "results", "type": "hist",
            "title": "Distribution of per-session profit",
            "xlabel": "profit (units)", "ylabel": "number of sessions",
            "series": [{"label": s, **_hist(results[s])} for s in results],
        })

    survival = bundle.get("survival")
    if (survival):
        plots.append({
            "id": "survival", "type": "hist",
            "title": "How long the player lasts before being barred / ruined",
            "xlabel": "hands played in a session", "ylabel": "number of sessions",
            "series": [{"label": s, **_hist(survival[s])} for s in survival],
        })

    heat = bundle.get("heat")
    if (heat):
        plots.append({
            "id": "heat", "type": "line",
            "title": "Heat: profit vs detection as the ramp steepens",
            "xlabel": "ramp (units per true count)", "ylabel": "value",
            "x": [_f(r[0], 2) for r in heat],
            "series": [
                {"label": "EV / hand", "y": [_f(r[1]) for r in heat]},
                {"label": "hands / session", "y": [_f(r[2], 1) for r in heat]},
                {"label": "total / session", "y": [_f(r[3], 2) for r in heat]},
                {"label": "P(barred)", "y": [_f(r[4]) for r in heat]},
            ],
        })

    risk = bundle.get("risk")
    if (risk):
        plots.append({
            "id": "risk", "type": "line",
            "title": "Risk of ruin vs bet aggressiveness (Kelly fraction)",
            "xlabel": "Kelly fraction", "ylabel": "value",
            "x": [_f(r[0], 2) for r in risk],
            "series": [
                {"label": "risk of ruin", "y": [_f(r[1]) for r in risk]},
                {"label": "median growth (x)", "y": [_f(r[2]) for r in risk]},
                {"label": "median drawdown", "y": [_f(r[4]) for r in risk]},
            ],
        })

    return plots


def _tables(cfg, bundle):
    tables = []
    summary = bundle.get("summary")
    if (summary):
        tables.append({
            "title": "Per-strategy results",
            "columns": ["strategy", "wagered", "profit", "edge %"],
            "rows": [[s, "%.0f" % w, "%.0f" % p, "%+.4f" % e] for (s, w, p, e) in summary],
        })
    trials = bundle.get("trials")
    if (trials):
        import numpy as np
        ntrials = max((len(a["hands"]) for a in trials.values()), default=0)
        rows = []
        for s, a in trials.items():
            n = max(1, len(a["hands"]))
            hands = np.array(a["hands"])
            profit = np.array(a["profit"])
            edge = 100.0 * float(profit.sum()) / a["wagered"] if a["wagered"] > 0 else 0.0
            rows.append([s, "%.0f%%" % (100.0 * a["ruined"] / n), "%.0f%%" % (100.0 * a["barred"] / n),
                         "%d" % int(np.median(hands)), "%+.0f" % np.median(profit),
                         "%+.0f .. %+.0f" % (np.percentile(profit, 10), np.percentile(profit, 90)),
                         "%+.3f%%" % edge])
        tables.append({
            "title": "Per-session outcomes over %d trials" % ntrials,
            "columns": ["strategy", "P(ruin)", "P(bar)", "med.hands", "med.profit",
                        "profit p10-p90", "pooled edge"],
            "rows": rows,
        })
    heat = bundle.get("heat")
    if (heat):
        tables.append({
            "title": "Heat sweep",
            "columns": ["ramp", "ev/hand", "hands/sess", "total/sess", "P(barred)"],
            "rows": [["%.1f" % r[0], "%.4f" % r[1], "%.0f" % r[2], "%.1f" % r[3],
                      "%.1f%%" % (r[4] * 100)] for r in heat],
        })
    risk = bundle.get("risk")
    if (risk):
        tables.append({
            "title": "Risk vs Kelly fraction",
            "columns": ["kelly", "RoR", "med.growth", "med.drawdown"],
            "rows": [["%.2f" % r[0], "%.1f%%" % (r[1] * 100), "%.2fx" % r[2],
                      "%.1f%%" % (r[4] * 100)] for r in risk],
        })
    ceiling = bundle.get("ceiling")
    if (ceiling):
        keys = [("opt_over_basic_pct", "perfect play over basic"),
                ("hilo_over_basic_pct", "Hi-Lo deviations over basic"),
                ("opt_over_hilo_pct", "perfect play over Hi-Lo")]
        tables.append({
            "title": "Playing ceiling (edge per hand)",
            "columns": ["comparison", "edge/hand %"],
            "rows": [[name, "%+.4f" % ceiling[k]] for (k, name) in keys if k in ceiling],
        })
    return tables


def results_to_json(cfg, bundle, log):
    return {
        "ok": True,
        "experiment": cfg.experiment,
        "config": cfg.to_dict(),
        "log": log,
        "plots": _plots(cfg, bundle),
        "tables": _tables(cfg, bundle),
        "error": None,
    }


def run_config(params, outdir="results", cancel=None, progress=None):
    """The front-end seam: untrusted config dict in, JSON-serializable dict out."""
    import experiment
    try:
        cfg = make_config(params)
    except Exception as e:
        return {"ok": False, "error": "bad config: %s" % e, "plots": [], "tables": []}
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            bundle = experiment.run(cfg, outdir, save_plots=False,
                                    cancel=cancel, progress=progress) or {}
    except Exception as e:
        return {"ok": False, "experiment": getattr(cfg, "experiment", None),
                "config": cfg.to_dict(), "log": log.getvalue(),
                "plots": [], "tables": [], "error": str(e)}
    return results_to_json(cfg, bundle, log.getvalue())


def main(argv):
    params = json.loads(argv[1]) if (len(argv) > 1) else {}
    out = run_config(params)
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv)
