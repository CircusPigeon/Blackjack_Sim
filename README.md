# Blackjack Lab

A from-scratch blackjack engine and advantage-play research lab. One config-driven
runner measures basic strategy, card counting, shuffle tracking, the casino
detection ("heat") game, bankroll risk-of-ruin, and the composition-exact
theoretical ceiling.

## Requirements

Python 3.9+ with `numpy`, `pandas`, `matplotlib`. (The bundled `venv/` is a stale
macOS artifact — ignore it; use a system Python.)

## Quick start

A point-and-click front-end (dropdowns for the config, checkboxes for the plots):

```
python gui.py
```

Or the CLI:

```
python main.py game
python main.py heat
python main.py bankroll
python main.py ceiling
```

Every flag is a `Config` field (see `config.py`). Examples:

```
python main.py game strategies=BASIC,COUNT,TRACK shuffle=casino dummyPlayers=4
python main.py game strategies=BASIC,COUNT,ORACLE     # Hi-Lo vs EoR betting
python main.py game shuffle=csm                       # continuous shuffler kills the count
python main.py game blackjackPays=1.2                 # 6:5 instead of 3:2
python main.py ceiling ceiling_samples=40000
```

Tables print to stdout; CSV/JSON records and PNG plots land in `results/`.

## Experiments (`experiment=`)

| kind | measures |
|---|---|
| `game` | per-strategy edge + edge-by-true-count over `rounds` dealt hands |
| `heat` | total profit vs ramp aggressiveness under casino back-off |
| `bankroll` | risk of ruin / growth / drawdown vs Kelly fraction |
| `ceiling` | composition-exact perfect play vs basic / Hi-Lo, by penetration |

## Strategies (sit any mix at one table, same shoes)

- `BASIC`, `DEALER` (mimic), `RANDOM`, `STAND` — baselines
- `COUNT` — Hi-Lo: bet spread + Illustrious-18 deviations
- `ORACLE` — effect-of-removal (best *linear*) betting weights
- `TRACK` — shuffle tracker: predicts high-card slugs from the pre-shuffle pile

## Module map

```
play.py        Play enum
deck.py        the shoe: dealing, Hi-Lo + EoR counts, shuffle hook, carryover
player/dealer/guest.py   actors (hands, money, per-strategy decisions)
strategy.py    basic strategy tables + Hi-Lo deviations + surrender
shuffle.py     shuffle procedures: GSR riffle / strip / cut, CSM
tracker.py     shuffle-tracking position-transition matrix
blackjack.py   the round engine (deal, play, settle, record)
config.py      the Config dataclass (one object = one reproducible run)
experiment.py  run(config) dispatcher + run_experiment primitive
analysis.py    record aggregation, tables, plots, CSV/JSON export
bankroll.py    counter calibration + fractional-Kelly risk-of-ruin Monte Carlo
heat.py        the detection / back-off game
ca.py          combinatorial-analysis playing ceiling
main.py        CLI
```

## What composes

The `game` engine is the ground truth: rules, shuffle, dummy players, any mix of
strategies, and the live **heat** (`heat_live=true`, casino back-off) and
**bankroll** (`bankroll_live=true`, fractional Kelly + ruin) layers all stack in
one run on shared shoes:

```
python main.py game strategies=BASIC,COUNT,TRACK shuffle=casino \
    dummyPlayers=4 heat_live=true bankroll_live=true
```

That single run plays a realistic session — a counter and a shuffle tracker bet
fractional Kelly off finite bankrolls at a full table against a real casino
shuffle, while the pit watches their bet/count slope and backs them off. (An
emergent result: the tracker survives longer than the counter, because its bets
track slugs rather than the visible count, so it's harder to spot.)

Add `trials=N` to Monte-Carlo that composed session over N seeds and get the
outcome *distribution* (ruin/bar rates, survival-hand percentiles, a histogram)
instead of one realization — each session ends early when the heroes leave, so a
few hundred to a few thousand trials runs in minutes:

```
python main.py game strategies=BASIC,COUNT,TRACK shuffle=casino \
    dummyPlayers=4 heat_live=true bankroll_live=true rounds=5000 trials=500
```

(`rounds` is the per-session horizon; cap it at a realistic session length to get
"P(barred within one session)". A literal million trials is the calibration-based
`heat`/`bankroll` experiments' job — those resample fast but aren't composed.)

The `heat` / `bankroll` / `ceiling` **experiments** remain as fast batch tools
(Monte-Carlo sweeps over a cached calibration, or pure combinatorics) for
*distributions* rather than single sessions. Only composition-exact **perfect
play** stays outside the live engine (~ms/decision); it lives in `ceiling`.

## Selected findings

- Basic strategy ≈ −0.5%; Hi-Lo counting flips it positive.
- 6:5 payouts cost ≈ 1.2% and counting can't overcome them; a CSM zeroes the count.
- A 2–3 riffle casino shuffle stays trackable; the tracker beats weak shuffles
  (≈ +1.2% at 1M hands) but the cut card neutralizes it.
- More players don't change per-hand EV (the "card-eater" myth) — they cut $/hour.
- Full Kelly ≈ 44% chance of losing half your roll; half-Kelly is the sweet spot.
- Hi-Lo already sits at the linear betting ceiling (EoR gains ≈ 0); perfect play
  beats basic by only +0.08% off the top, rising to +0.46% deep in the shoe.

## Caveats

Splits and the full Illustrious-18 index set are partial; the CA oracle uses the
fixed-composition-within-a-hand approximation; risk sims resample i.i.d. hands
(no within-shoe serial correlation).

## Roadmap

- A composition-exact **PERFECT** playing strategy as an in-engine player
  (currently `ceiling`-only; ~ms/decision, so benchmark-scale rather than 1M-hand).
- Web export: precompute sweeps → JSON → interactive charts.
```
