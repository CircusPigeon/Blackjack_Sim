"""Config-driven experiment runner.

run(config) dispatches on config.experiment and performs one of:
  game     -- play the card engine, report per-strategy edge + edge-by-true-count
  heat      -- the detection game: sweep ramp aggressiveness vs casino backoff
  bankroll  -- fractional-Kelly risk of ruin / growth sweep
  ceiling   -- composition-exact playing ceiling (combinatorial analysis)

The heat and bankroll experiments derive a counter calibration from the same
engine (cached on disk), and the ceiling experiment uses the same rules. Heavy
modules are imported lazily so a single experiment only pulls in what it needs."""

import os
import random
import numpy as np
import analysis as A
from blackjack import Blackjack, COUNTERS


def run_experiment(config, verbose=False, record=True, cancel=None, progress=None):
    """The card-game primitive: play config.rounds seeded hands, return the game.
    cancel (if given) is called periodically and may raise to abort the run;
    progress(done, total, label) is called periodically for UI feedback."""
    random.seed(config.seed)
    game = Blackjack(config=config, verbose=verbose, record=record)
    step = max(1, config.rounds // 100)
    for i in range(config.rounds):
        game.run()
        if (cancel is not None and (i & 1023) == 0):
            cancel()
        if (progress is not None and i % step == 0):
            progress(i, config.rounds, "hands")
    return game


def edges(game):
    """Final per-strategy edge (%) for the tracked guests of a finished game."""
    return {game.players[i].strategy: game.players[i].getEdge() * 100.0
            for i in range(game.numTracked)}


def run(config, outdir="results", save_plots=True, cancel=None, progress=None):
    """Run the experiment selected by config.experiment. save_plots=False skips
    writing PNG/CSV/JSON (the returned dict carries the plot data so a GUI can
    render figures itself). cancel/progress, if given, are callables for abort
    and UI feedback."""
    os.makedirs(outdir, exist_ok=True)
    kind = config.experiment
    if (kind == "game"):
        return _run_game(config, outdir, save_plots, cancel, progress)
    if (kind == "heat"):
        return _run_heat(config, outdir, save_plots)
    if (kind == "bankroll"):
        return _run_bankroll(config, outdir, save_plots)
    if (kind == "ceiling"):
        return _run_ceiling(config, outdir, save_plots, cancel)
    raise ValueError("unknown experiment '" + str(kind) + "' (game|heat|bankroll|ceiling)")


def _fmt(e):
    return "%+.4f%%" % e


def _pick_hero(strategies):
    for s in ("COUNT", "ORACLE", "TRACK", "BASIC", "DEALER"):
        if (s in strategies):
            return s
    return strategies[0] if strategies else None


def _calibration():
    import bankroll
    return bankroll.calibrate(bankroll.load_or_make_calibration())


def _run_game(config, outdir, save_plots=True, cancel=None, progress=None):
    if (config.trials > 1):
        return _run_game_trials(config, outdir, save_plots, cancel, progress)
    game = run_experiment(config, record=True, cancel=cancel, progress=progress)
    rec = game.records
    rows = A.summary(rec)
    print("[%s]  %d hands | shuffle=%s | dummies=%d"
          % (config.label, config.rounds, config.shuffle, config.dummyPlayers))
    A.print_table([(s, "%.0f" % w, "%.0f" % p, _fmt(e)) for (s, w, p, e) in rows],
                  ["strategy", "wagered", "profit", "edge"])

    present = [r[0] for r in rows]
    hero = next((s for s in ("COUNT", "ORACLE", "TRACK", "BASIC") if s in present), None)
    edge_rows = {}
    if (hero):
        tc_rows = A.edge_by_true_count(rec, hero)
        edge_rows[hero] = tc_rows
        print("\nEdge by true count [%s]:" % hero)
        A.print_table([(b, n, _fmt(e)) for (b, n, e) in tc_rows],
                      ["true_count", "hands", "edge"])
        if (save_plots):
            A.plot_edge_by_true_count(rec, hero, os.path.join(outdir, config.label + "_edge.png"))

    if (config.heat_live or config.bankroll_live):
        print("\nLive hero outcome (one composed session):")
        srows = []
        for g in game.guests:
            if (g.strategy in COUNTERS):
                status = "ruined" if g.ruined else ("barred" if g.barred else "still in")
                srows.append((g.strategy, "%.0f" % g.money, g.handsPlayed, status))
        A.print_table(srows, ["strategy", "final_roll", "hands_played", "status"])
        if (config.bankroll_live and save_plots):
            A.plot_bankroll(rec, os.path.join(outdir, config.label + "_bankroll.png"))

    if (save_plots):
        A.export_csv(rec, os.path.join(outdir, config.label + ".csv"))
        A.export_meta(config.to_dict(), rows, os.path.join(outdir, config.label + ".json"))
        print("\nWrote " + os.path.join(outdir, config.label + ".{csv,json}"))
    return {"summary": rows, "edges": edges(game), "records": rec, "hero": hero, "edge_rows": edge_rows}


def _run_game_trials(config, outdir, save_plots=True, cancel=None, progress=None):
    """Repeat the session config.trials times with different shuffles and report
    the distribution of per-session outcomes for every tracked strategy. Works for
    any strategy (BASIC included): the profit distribution shows the variance. With
    live heat/bankroll you also get bar/ruin rates and a survival distribution. A
    trial ends early only once every tracked player has left the table."""
    tracked = list(config.strategies)
    hero = _pick_hero(tracked)
    agg = {s: {"hands": [], "profit": [], "wagered": 0.0,
               "ruined": 0, "barred": 0} for s in tracked}
    edge_acc = {}                                       # pooled edge-by-true-count
    trajectories = []                                   # hero balance path per trial (first few)
    for t in range(config.trials):
        if (cancel is not None):
            cancel()
        if (progress is not None):
            progress(t, config.trials, "trials")
        random.seed(config.seed + t)
        game = Blackjack(config=config, verbose=False, record=True)
        for _ in range(config.rounds):
            game.run()
            if (all(g.out for g in game.guests)):     # nobody left to simulate
                break
        A.accumulate_edge(game.records, edge_acc)      # fold this trial in, then drop it
        if (hero is not None and len(trajectories) < 60):
            rec = game.records
            path = [rec["bankroll"][i] for i in range(len(rec["round"]))
                    if rec["strategy"][i] == hero]
            if (path):
                trajectories.append(path)
        for g in game.guests:
            a = agg[g.strategy]
            a["hands"].append(g.handsPlayed)
            a["profit"].append(g.money - g.startMoney)
            a["wagered"] += g.totalWagered
            a["ruined"] += int(g.ruined)
            a["barred"] += int(g.barred)

    n = config.trials
    print("[%s]  %d trials x up to %d hands  (heat_live=%s, bankroll_live=%s, shuffle=%s, dummies=%d)"
          % (config.label, n, config.rounds, config.heat_live, config.bankroll_live,
             config.shuffle, config.dummyPlayers))
    rows = []
    for s in tracked:
        a = agg[s]
        hands = np.array(a["hands"])
        profit = np.array(a["profit"])
        edge = 100.0 * float(profit.sum()) / a["wagered"] if a["wagered"] > 0 else 0.0
        rows.append((s,
                     "%.0f%%" % (100.0 * a["ruined"] / n),
                     "%.0f%%" % (100.0 * a["barred"] / n),
                     "%d" % int(np.median(hands)),
                     "%+.0f" % np.median(profit),
                     "%+.0f .. %+.0f" % (np.percentile(profit, 10), np.percentile(profit, 90)),
                     "%+.3f%%" % edge))
    A.print_table(rows, ["strategy", "P(ruin)", "P(bar)", "med.hands",
                         "med.profit", "profit p10-p90", "pooled edge"])
    survival = {s: agg[s]["hands"] for s in tracked}
    results = {s: agg[s]["profit"] for s in tracked}
    edge_rows = {s: A.edge_rows_from_acc(edge_acc, s) for s in tracked}
    if (save_plots):
        A.plot_survival_hist(survival, os.path.join(outdir, config.label + "_survival.png"))
        print("Wrote results/" + config.label + "_survival.png")
    return {"trials": agg, "survival": survival, "results": results,
            "edge_rows": edge_rows, "hero": hero, "trajectories": trajectories}


def _run_heat(config, outdir, save_plots=True):
    import heat
    calib = _calibration()
    slopes = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0]
    rows = heat.aggressiveness_sweep(calib, slopes, threshold=config.heat_threshold,
                                     warmup=config.heat_warmup, base_rate=config.heat_rate,
                                     pivot=config.ramp_start, min_bet=config.spread_min,
                                     max_bet=config.spread_max, maxHands=config.heat_maxHands,
                                     seed=config.seed)
    print("[heat] casino backoff threshold=%.1f, spread %g-%g units from TC %g, session <= %d hands"
          % (config.heat_threshold, config.spread_min, config.spread_max,
             config.ramp_start, config.heat_maxHands))
    A.print_table([("%.1f" % s, "%.4f" % ev, "%.0f" % ln, "%.1f" % tot, "%.1f%%" % (pb * 100))
                   for (s, ev, ln, tot, pb) in rows],
                  ["ramp", "ev/hand", "hands/sess", "total/sess", "P(barred)"])
    if (save_plots):
        A.plot_heat_curve(rows, os.path.join(outdir, "heat_curve.png"))
    best = max(rows, key=lambda r: r[3])
    print("optimal ramp ~%.1f units/TC (total %.1f)." % (best[0], best[3]))
    return {"heat": rows}


def _run_bankroll(config, outdir, save_plots=True):
    import bankroll
    calib = _calibration()
    print("[bankroll] edge %+.4f%%/unit, N0 %.0f hands. B0=%.0f units, ruin at %.0f%%, horizon %d"
          % (calib["edge_bw"] * 100, calib["n0"], config.bankroll_units,
             config.ruin_frac * 100, config.bankroll_horizon))
    fractions = [0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    rows = bankroll.risk_curve(calib, fractions, B0=config.bankroll_units, table_max=500.0,
                               ruin_frac=config.ruin_frac, goal_mult=0,
                               maxHands=config.bankroll_horizon, M=8000, seed=config.seed)
    A.print_table([("%.2f" % f, "%.1f%%" % (ror * 100), "%.2fx" % g, "%.1f%%" % (dd * 100))
                   for (f, ror, g, pg, dd) in rows],
                  ["kelly", "RoR", "med.growth", "med.DD"])
    if (save_plots):
        A.plot_risk_curve(rows, os.path.join(outdir, "risk_vs_kelly.png"))
    return {"risk": rows}


def _run_ceiling(config, outdir, save_plots=True, cancel=None):
    import ca
    from deck import _EOR_BASE, EOR_SCALE
    print("[ceiling] composition-exact playing ceiling, %d samples (h17=%s)"
          % (config.ceiling_samples, config.hitSoft17))
    print("\nEoR-optimal betting weights (Hi-Lo is a coarse rounding of these):")
    hilo = {1: -1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1}
    label = {1: "A", 10: "T"}
    A.print_table([(label.get(c, str(c)), "%+.2f" % _EOR_BASE[c],
                    "%+.2f" % (_EOR_BASE[c] * EOR_SCALE), "%+d" % hilo[c]) for c in range(1, 11)],
                  ["card", "EoR%", "EoR tag", "Hi-Lo"])

    r = ca.measure_playing_ceiling(n_samples=config.ceiling_samples,
                                   h17=config.hitSoft17, seed=config.seed, cancel=cancel)
    print("\nPlay (flat bet, all penetrations):")
    A.print_table([("perfect over basic", _fmt(r["opt_over_basic_pct"])),
                   ("Hi-Lo dev over basic", _fmt(r["hilo_over_basic_pct"])),
                   ("perfect over Hi-Lo", _fmt(r["opt_over_hilo_pct"]))],
                  ["comparison", "edge/hand"])

    print("\nPlay ceiling by penetration:")
    band_n = max(10000, config.ceiling_samples // 4)
    prows = []
    for (lo, hi) in [(0, 40), (40, 100), (100, 170), (170, 234)]:
        b = ca.measure_playing_ceiling(n_samples=band_n, h17=config.hitSoft17,
                                       seed=config.seed + 1, rem_lo=lo, rem_hi=hi, cancel=cancel)
        prows.append(("%d-%d" % (lo, hi), _fmt(b["opt_over_basic_pct"]),
                      "%.1f" % ((312 - (lo + hi) / 2) / 52.0)))
    A.print_table(prows, ["cards dealt", "perfect-basic", "decks left"])
    return {"ceiling": r}
