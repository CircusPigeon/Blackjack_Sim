# Blackjack Lab

A from-scratch blackjack engine and advantage-play research lab. One config-driven
runner measures basic strategy, card counting, shuffle tracking, the casino
detection ("heat") game, bankroll risk-of-ruin, and the composition-exact
theoretical ceiling.

## Run it yourself

Python 3.9+ on Windows, macOS, or Linux.

```
git clone <this-repo>
cd Blackjack_Sim
pip install -r requirements.txt      # numpy + matplotlib
python gui.py
```

`tkinter` (the GUI toolkit) ships with CPython; on Debian/Ubuntu install it with
`sudo apt install python3-tk`. `pandas` is optional (CSV/DataFrame export only).

A point-and-click front-end — dropdowns for the config, checkboxes for the plots,
live progress, and a "Save plots" toggle:

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
| `ceiling` | composition-exact perfect play vs basic / Hi-Lo, by penetration (respects H17/S17, surrender, deck count; no splits) |

## Strategies (sit any mix at one table, same shoes)

- `BASIC`, `DEALER` (mimic), `RANDOM`, `STAND` — baselines
- `COUNT` — Hi-Lo: bet spread + Illustrious-18 deviations
- `ORACLE` — effect-of-removal (best *linear*) betting weights
- `TRACK` — shuffle tracker: predicts high-card slugs from the pre-shuffle pile

## What the algorithms do

**COUNT — Hi-Lo card counter (the practical human strategy).** Running count:
**+1** per 2–6, **0** per 7–9, **−1** per 10/J/Q/K/A; divide by the decks remaining
to get the **true count (TC)**, an estimate of how rich the unseen cards are. One
number drives both (a) **bet sizing** — a linear ramp on TC (flat minimum below
`ramp_start`, then `spread_slope` extra units per +1 TC, capped at `spread_max`)
— and (b) **play** — basic strategy plus a subset of the Hi-Lo "Illustrious-18"
index deviations (override basic when the TC crosses a cell's threshold; e.g.
stand 16 vs 10 at TC ≥ 0, insure at TC ≥ +3).

**ORACLE — the best *linear* betting count for our exact game.** Plays
*identically* to COUNT (same deviations) — deliberately, to isolate one question:
*can smarter bet-sizing weights beat Hi-Lo's?* The only difference is the count it
bets on: an **effect-of-removal (EoR)** count whose per-rank tags are proportional
to how much removing one card of each rank shifts the player's edge in *this* rule
set (H17 + surrender). Those weights are derived from the engine by regressing
realized flat-bet edge on the remaining-shoe composition (`precompute_eor.py`),
then balanced and scaled to the Hi-Lo magnitude. ORACLE marks the betting ceiling
among linear counts — and the finding is that Hi-Lo already reaches it.

**TRACK — shuffle tracker.** Exploits the *sequence* correlation a weak casino
shuffle leaves behind (which counting ignores). It learns the shuffle by
simulating the dealer's exact procedure ~4000× into a **position-transition
matrix** `T[i,d]` = P(a card at pre-shuffle pile position *i* is dealt at step
*d*); one matrix–vector product then forecasts the expected Hi-Lo richness at each
upcoming deal position. It bets the ramp on that *forecast* (not the running
count), betting up just before a high-card slug arrives, and plays basic strategy.
Idealized full-knowledge tracker (sees the whole pre-shuffle pile) → an *upper
bound* on tracking; the cut card is the casino's main defense.

**CEILING — composition-exact perfect play (an analysis, not a player; `ca.py`).**
For thousands of sampled (remaining composition, your two cards, dealer upcard)
states it computes, by dynamic programming, the dealer's exact final-total
distribution and the exact EV of stand / hit / double / **late surrender** under
the *actual* composition, then takes the max-EV action. It reports perfect-play
edge − basic-strategy edge, averaged by penetration — the **upper bound on playing
edge**. Respects **H17/S17, late surrender, and deck count**; pairs are played by
total (**splits not modeled**), so it is the *no-split* playing ceiling.

## Rules & terms

| term | meaning |
|---|---|
| **H17 / S17** | dealer hits / stands on soft 17 (an ace as 11, e.g. A-6). H17 is ~0.2% worse for the player. `hitSoft17` |
| **3:2 vs 6:5** | blackjack payout: 3:2 pays 1.5×; 6:5 pays 1.2× and costs the player ≈ 1.3%. `blackjackPays` |
| **late surrender** | forfeit half the bet and fold after seeing your two cards and the dealer upcard (first decision only, after the dealer checks for blackjack). `surrender` |
| **penetration** | fraction of the shoe dealt before the cut card forces a reshuffle (0.75 = 75%); deeper helps a counter. `penetration` |
| **decks** | number of 52-card packs in the shoe (Vegas: 6 or 8). `numPacks` |
| **true count (TC)** | running count ÷ decks remaining — normalizes the count for shoe depth |
| **bet spread / ramp** | how a counter scales bets with TC: `spread_min`–`spread_max` units, climbing `spread_slope` units per +1 TC from `ramp_start` |
| **casino shuffle** | a realistic hand shuffle — N GSR riffles + strips + a final cut (`shuffleRiffles/Strips/Cut`); not fully randomizing, hence trackable |
| **CSM** | continuous shuffle machine — dealt cards return to the shoe each hand, so no count ever builds (`shuffle=csm`) |
| **dummy players** | untracked bystanders who consume cards; they don't change your per-hand edge, only hands/hour |
| **Kelly fraction** | bet size as a fraction of the growth-optimal (full-Kelly) bet; < 1 trades growth for lower risk of ruin. `kelly_fraction` |
| **heat / back-off** | the pit estimating your bet-vs-count slope and barring you once it looks like counting. `heat_*` |

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
make_figures.py  regenerate the curated write-up figures (SVG/PNG) + manifest
```

## Figures for the write-up

`make_figures.py` regenerates the curated figure set from pinned, reproducible
Configs and writes them (SVG + PNG) plus a `figures/manifest.json` of the headline
numbers — so a write-up can quote one source of truth and stay in sync with the
images. Every edge estimate is Monte-Carlo: each condition runs over many
independent trials and is shown as a mean with a **95% confidence interval**
(paired comparisons like TRACK vs BASIC are differenced per trial to cancel
shoe-to-shoe noise).

```
python make_figures.py --list                 # list the figure specs
python make_figures.py                         # regenerate everything (minutes)
python make_figures.py --only heat,penetration
python make_figures.py --trials 40 --rounds 60000   # higher fidelity, slower
python make_figures.py --smoke                 # tiny sizes, just to test plumbing
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
- 6:5 payouts cost ≈ 1.3% and counting can't overcome them; a CSM zeroes the count.
- A 2–3 riffle casino shuffle stays trackable; the tracker beats weak shuffles
  (≈ +1.0–1.8%/hand, more the sloppier the shuffle), and the final cut sharply
  reduces it (the casino's main defense).
- More players don't change per-hand EV (the "card-eater" myth) — they cut hands/hour.
- Full Kelly ≈ 46% chance of losing half your roll; half-Kelly (~14%) is the sweet spot.
- **Hi-Lo sits at the linear betting ceiling** — the EoR-optimal weights for our game
  tie it. **But it's far below the playing ceiling:** composition-perfect play beats
  basic by ≈ +0.27%/hand off the top, rising to ≈ +0.76% deep in the shoe, while
  Hi-Lo's index plays capture almost none of that (≈ 0.02–0.06%).

## Caveats

The CA ceiling plays pairs by total (**no splits**) and uses the
fixed-composition-within-a-hand approximation — it *does* respect H17/S17, late
surrender, and deck count. The counter's Illustrious-18 deviation set is a subset
using textbook thresholds rather than engine-derived ones (worth only
≈ 0.02–0.06%/hand, so low impact). ORACLE deliberately plays like COUNT (it
isolates the *betting* count, not play). Risk sims resample i.i.d. hands (no
within-shoe serial correlation).

## Roadmap

- **Splits in the CA ceiling** (currently no-split): the standard two-independent-
  hands approximation, validated against the engine's split rules. Modest expected
  gain — the bulk of composition edge is in hard hit/stand/double/surrender cells.
- Engine-derived index-play thresholds for the active rule set (currently a textbook
  subset; low impact, but symmetric with the engine-derived EoR betting weights).
- A composition-exact **PERFECT** playing strategy as an in-engine player
  (currently `ceiling`-only; ~ms/decision, so benchmark-scale rather than 1M-hand).
- Website: precomputed figures (`make_figures.py`) + write-up; readers who want to
  run their own experiments clone the repo and launch `gui.py`.
```
