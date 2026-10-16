# Talent Scheduling Problem (CSPLib prob039) + Location/Travel Extension

## Problem
Given a set of scenes (each needing certain actors and having a duration)
and a daily cost per actor, find a shooting order that minimizes the total
cost of keeping actors on set. Each actor is paid from their first to their
last scheduled scene, but only the **waiting (idle) days** in between count
as cost, as in CSPLib prob039: `actorCost[a] = c[a] * (span of a - days a
works)`. The days an actor works are a constant, so they do not change which
order is optimal.

## Extension
Each scene also has a filming **location**, and moving the crew between
two different locations costs money (`travel[locA, locB]`). The extended
model jointly minimizes actor waiting cost **and** total travel cost, which
creates real tension: grouping an actor's scenes together to cut their
idle cost can scatter locations and raise travel cost, and vice versa.

## Requirements
- Python 3.12
- MiniZinc 2.10.1 (final tests run with the official standalone bundle
  from minizinc.org / GitHub releases; the Ubuntu `apt` package is 2.5.3)
- Chuffed solver (default; bundled with MiniZinc). Gecode also works via
  `--solver gecode` but is much slower on this problem (see Results).

## Usage
```bash
python3 proj.py --instance data/film2.json --model base
python3 proj.py --instance data/tradeoff_demo.json --model extended
```

`--model base` runs the CSPLib prob039 model (our own encoding, with
symmetry breaking and a redundant constraint).
`--model extended` runs our location/travel extension.

Options: `--solver` (default `chuffed`), `--time-limit` in seconds
(default 60), `--verbose` (raw solver output on stderr), `--std-globals`
(passes `-G std`; only needed for a globals type error on some apt
installs). The last line of the output says whether the result is proved
optimal or just the best found within the time limit.

After solving, `proj.py` recomputes the schedule's cost in plain Python
(independently of MiniZinc) and checks it against the solver's value; a
mismatch aborts with exit code 3.

Suggested demo (fast): `data/tradeoff_demo.json` (proved optimal in 0.2 s)
and `data/film2.json --model base` (proves 87 in ~40 s; use
`--time-limit 90`).

## Instance format (JSON)
```json
{
  "numScenes": 6,
  "numActors": 4,
  "numLocations": 2,
  "ia": [[...]],       // numActors x numScenes, 1 if actor appears in scene
  "d": [...],          // duration of each scene
  "c": [...],          // daily cost per actor
  "loc": [...],        // location id of each scene (extended model only)
  "travel": [[...]]    // numLocations x numLocations travel cost matrix
}
```

## Comparison with existing online MiniZinc models (not in CSPLib)

The CSPLib page for prob039 ("The Rehearsal Problem") links to `rehearsal.mzn`
as its official model. Outside CSPLib, at least two other public MiniZinc
models exist for this problem:
- `talent_scheduling.mzn` / `talent_scheduling_alt.mzn` in the official
  `MiniZinc/minizinc-benchmarks` GitHub repository (Stuckey, 2008;
  `_alt` version originally for Paul Shaw's solver, modified by Barbara
  Smith, converted to MiniZinc by Peter J. Stuckey).
- `talent.mzn` on hakank.org (Håkan Kjellerstrand), a port of an ILOG OPL
  example.

**We did not use or consult these models while building `base.mzn` or
`extended.mzn`.** Both were developed from scratch from the CSPLib prob039
specification. We compared our finished model against
`talent_scheduling_alt.mzn` afterwards, out of curiosity and to write this
section honestly:

- **Same paradigm, developed independently.** Both models encode the
  schedule as a permutation of scenes and use `firstSlot`/`lastSlot`
  variables per actor — this is the standard vocabulary introduced by
  Barbara Smith (2003), cited by CSPLib itself, and is common to nearly
  every published model of this problem. It is not something we copied.
- **Different cost encoding.** We compute a running total of shooting
  days (`cumDur`, a prefix-sum array) and take a single difference,
  `cumDur[lastSlot[a]] - cumDur[firstSlot[a]-1]`, to get each actor's
  cost. `talent_scheduling_alt.mzn` instead splits the cost into two
  explicit terms (cost while filming + cost while idle,
  `wait[j]`), following the original Cheng (1993) formulation more
  literally.
- **Validated against the official CSPLib prob039 instances.** We ran
  `base.mzn` on the published Film1 and Film2 talent-scheduling instances
  (not the synthetic instances used for the performance benchmarks below).
  Film2 (13 scenes, 10 actors) proves optimal at **87** (×100 = 8700)
  with Chuffed in ~40 s, matching the published optimum exactly (Gecode
  does not prove it: best 130 after 2 min). Film1 (20 scenes, 8 actors)
  was not proved optimal (best found 210 in 150 s with Chuffed). We also verified our cost formulation against the synthetic instances
  used in the symmetry-breaking/search benchmarks below (373, 617, 823 on
  5/7/8-scene synthetic instances) — those instances aren't from CSPLib,
  so use the Film1/Film2 numbers above as the authoritative correctness check.
- **Performance depends heavily on the solver.** The benchmark against
  `talent_scheduling_alt.mzn` was done on an earlier version of `base.mzn`
  (no symmetry breaking / redundant constraints / search annotation) with
  Gecode 6.2.0 and is no longer representative; those were later added
  (next section). Current measurements are in "Results" below.

## Performance optimizations (added after benchmarking against the reference model)

We benchmarked our original `base.mzn`/`extended.mzn` against
`talent_scheduling_alt.mzn` and found our models correct but much slower
to prove optimality (see comparison section above). We investigated why
and made three findings, all independently verified:

**1. Symmetry breaking + a redundant span constraint make `base.mzn` far
faster, with identical results.** Adding
`constraint seq[1] < seq[numScenes];` (breaks the reversal symmetry: a
schedule and its mirror image cost the same when cost only depends on
actor span) and a redundant constraint
`lastSlot[a] - firstSlot[a] >= nAppear[a] - 1` (implied by the
definition of first/last slot, but stated explicitly to help
propagation), plus a `first_fail` search annotation, cut solve time by
2-3 orders of magnitude on our test instances (e.g. 3.3 s → 0.04 s on an
8-scene instance) while returning the exact same optimal costs on every
instance we could verify to completion. This optimized version is now
`models/base.mzn`.

**2. We found a real bug in the official reference model.** While
comparing search behaviour, we noticed `talent_scheduling_alt.mzn`
(MiniZinc/minizinc-benchmarks) reported a proven-optimal cost that was
*higher* than a valid schedule we found by hand-verifying in Python,
independent of any MiniZinc model. Tracing it down: the model's second
implied ordering constraint has
`forall(k,l in diffn where k < j)` — comparing an **actor** index `k`
against `j`, the **scene**-loop variable from the enclosing `forall`,
instead of comparing the two actor indices `k < l` to avoid duplicate
symmetric pairs. This typo makes the constraint unsound on some
instances, pruning away the true optimum. Fixing `k < j` to `k < l`
made the model correctly converge to the same (lower, correct) optimal
cost we had found independently.

**3. A symmetry-breaking constraint that's valid for `base.mzn` is
*not* valid for `extended.mzn`.** We initially added the same
`seq[1] < seq[numScenes]` symmetry breaking to `extended.mzn`, but it
silently returned a wrong (higher-cost) "optimal" result on a test
instance. Reason: reversing a schedule only preserves cost when cost is
symmetric under reversal. Actor waiting cost is (depends only on span),
but travel cost is not, since our `travel[locA, locB]` matrix is not
required to be symmetric (`travel[A,B]` need not equal `travel[B,A]`) —
reversing the schedule can change the total travel cost. We removed
that constraint from `extended.mzn`; it keeps the redundant span
constraint and search annotation, which are still sound and give a real
speed-up without this risk (e.g. 3260 → 2752 within the same 15 s
budget on an 11-scene test instance, both otherwise unproven within that
budget).

## Sanity check: extended model reduces to base model when travel = 0
Running `extended.mzn` on Film2 with an all-zero travel matrix
(`data/film2_ext_zero.json`) gives `TOTAL_ACTOR_COST=87,
TOTAL_TRAVEL_COST=0, TOTALCOST=87` — identical to the base model's
result on the same instance, confirming the extension doesn't change
behaviour when travel cost is absent.

## Known packaging note
On some MiniZinc/Gecode apt packages there's a version mismatch between
Gecode's bundled global-constraint redefinitions and the standard library,
producing a `global_cardinality` type error. If you hit it, pass
`--std-globals` to `proj.py`. It is off by default because `-G std`
decomposes `all_different`, which removes Chuffed's native version.

## Results (MiniZinc 2.10.1, this machine)
| Model / instance | Solver | Result |
|---|---|---|
| base, Film2 | Gecode | no proof in 2 min, best 130 |
| base, Film2 | Chuffed | **87 proved**, ~40 s |
| extended, Film2, travel = 0 | Chuffed | 87 proved (87 + 0), ~59 s |
| extended, tradeoff_demo | Chuffed | 85 proved (55 + 30), 0.2 s |
| base, Film1 (20 scenes) | Chuffed | 210 best in 150 s, not proved |
| extended, Film2 with travel (13 locations) | Chuffed | 136 best in 3 min, not proved |

## Use of AI tools (mandatory declaration)
- Claude Code (Anthropic) was used to review the models/README, run the
  tests above, add the `--time-limit`/`--solver`/status options to
  `proj.py`, and update this README with the measured results.
- Web resources: the public MiniZinc models `talent_scheduling_alt.mzn`
  (MiniZinc benchmarks) and `talent.mzn` (hakank.org) were only compared
  against after our models were written; they were not used as a basis
  (see the comparison section above).

## Files
- `models/base.mzn` — CSPLib prob039 base model
- `models/extended.mzn` — extended model with locations/travel
- `data/*.json` — instances (film1, film2, film2_ext, film2_ext_zero, tradeoff_demo); `data/rehearsal.dzn` is the raw CSPLib data (not read by `proj.py`)
- `proj.py` — pipeline: instance -> .dzn -> solve -> parse -> readable schedule

## Multi-objective strategy
The extended model combines two criteria, actor waiting cost and travel
cost, with a **weighted sum with equal weights**
(`totalCost = totalActorCost + totalTravelCost`). Both costs are in the same
monetary unit, so their sum is the real total production cost and needs no
arbitrary weights. A lexicographic order would let one criterion dominate
(e.g. ignore any travel saving once actor cost is minimal), and a Pareto
front would give many solutions with no natural way to pick one, when the
goal is a single cheapest schedule. The weighted sum finds the true minimum
total cost, and the `tradeoff_demo` instance shows the criteria really
conflict (actor-only optimum costs 110 in travel; joint optimum is 85).

## Trade-off example (`data/tradeoff_demo.json`, 5 scenes, 2 actors)
The extended model's optimal schedule has `TOTAL_ACTOR_COST=55,
TOTAL_TRAVEL_COST=30, TOTALCOST=85`. Minimizing only the actor cost gives
actor cost 0 with order 1,3,2,4,5, but under the real travel matrix that
order costs 90+10+0+10 = 110 travel, so the joint objective changes the
optimum.
