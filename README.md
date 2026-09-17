# Talent Scheduling Problem (CSPLib prob039) + Location/Travel Extension

## Problem
Given a set of scenes (each needing certain actors and having a duration)
and a daily cost per actor, find a shooting order that minimizes the total
cost of keeping actors on set, paid from their first to last scheduled
scene inclusive of any waiting days in between.

## Extension
Each scene also has a filming **location**, and moving the crew between
two different locations costs money (`travel[locA, locB]`). The extended
model jointly minimizes actor waiting cost **and** total travel cost, which
creates real tension: grouping an actor's scenes together to cut their
idle cost can scatter locations and raise travel cost, and vice versa.

## Requirements
- Python 3.12
- MiniZinc 2.10.1 recommended (developed/tested here against 2.8.2 with
  Gecode 6.2.0; see note below if you hit a solver error)
- Gecode solver (bundled with the MiniZinc bundled distribution, or
  `apt install minizinc` on Ubuntu)

## Usage
```bash
python3 proj.py --instance data/example_instance.json --model base
python3 proj.py --instance data/example_instance.json --model extended
```

`--model base` runs the unmodified CSPLib prob039 model.
`--model extended` runs our location/travel extension.

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
- **Same optimal cost, verified empirically.** On several small test
  instances solved to proven optimality, both models return identical
  optimal costs (e.g. 373, 617, 823 on 5/7/8-scene instances) — the two
  cost formulations are mathematically equivalent.
- **Different performance — ours is notably slower.** `talent_scheduling_alt.mzn`
  adds symmetry breaking (`s[1] < s[numScenes]`), Barbara Smith's
  redundant constraints on wait times and scene ordering, and a custom
  search annotation (`int_search(s, first_fail, indomain, complete)`).
  Our `base.mzn` has none of these. Benchmarked with Gecode 6.2.0 on
  synthetic instances:

  | Instance | Our `base.mzn` | `talent_scheduling_alt.mzn` |
  |---|---|---|
  | 8 scenes, 4 actors | 3.77 s (proven optimal) | 0.002 s (proven optimal) |
  | 12 scenes, 6 actors | timeout at 30 s (best found: 3760) | 0.13 s (proven optimal: 2287) |
  | 16 scenes, 8 actors | timeout at 30 s (4288) | timeout at 30 s (3242) |
  | 20 scenes, 9 actors | timeout at 30 s (7060) | timeout at 30 s (6275) |

  Adding just the symmetry-breaking constraint to our model helps
  (3760 → 2630 on the 12-scene instance) but does not close the gap on
  its own — the combination of redundant constraints and search
  strategy is what makes the reference model scale better.

**Takeaway for the writeup:** our model is correct (matches the reference
model's optimal costs wherever both can be checked) but not as
search-efficient at larger sizes, since we did not add symmetry breaking,
redundant constraints, or a custom search strategy. This is a known
trade-off in CP modelling (declarative clarity vs. solver-guided
performance) worth naming explicitly rather than hiding.

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
cost we had found independently. This is a good, concrete thing to
mention in the video as evidence of having actually understood and
stress-tested the models compared, not just skimmed them.

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

**Takeaway for the writeup/video:** solution quality (optimal cost) was
correct from the start; performance needed genuine CP techniques
(symmetry breaking, redundant/implied constraints, search strategy) to
scale, and applying them uncritically to the extended model would have
introduced a silent bug — a useful cautionary example of why symmetry
arguments need re-checking whenever a model's cost structure changes.

## Known packaging note
On some MiniZinc/Gecode apt packages there's a version mismatch between
Gecode's bundled global-constraint redefinitions and the standard library,
producing a `global_cardinality` type error. `proj.py` already works
around this with the `-G std` flag when invoking MiniZinc. If you install
the official 2.10.1 bundle from minizinc.org instead of via apt, you
likely won't need this workaround, but it's harmless either way.

## Files
- `models/base.mzn` — CSPLib prob039 base model
- `models/extended.mzn` — extended model with locations/travel
- `data/example_instance.json` — example instance (6 scenes, 4 actors, 2 locations)
- `proj.py` — pipeline: instance -> .dzn -> solve -> parse -> readable schedule

## For the 1-page PDF writeup
- CSPLib problem number: prob039 (Talent Scheduling / Rehearsal Problem)
- Extension: joint minimization of actor waiting cost and inter-location
  travel cost, via a new `loc`/`travel` data and objective term.
- Include a concrete example (like the one above) showing the extended
  model trading a small actor-cost increase for a travel-cost saving,
  since that's the clearest evidence the extension is non-trivial.
- Multi-objective strategy: name and justify the approach taken
  (lexicographic vs. Pareto vs. weighted sum — see project notes) for
  combining actor cost and travel cost, since the extension optimizes
  more than one criterion.
- Online MiniZinc model declaration: state explicitly that
  `talent_scheduling_alt.mzn` (MiniZinc/minizinc-benchmarks) and
  `talent.mzn` (hakank.org) were found and compared against, but not
  used as a basis for our implementation — see the comparison section
  above for the full analysis (same paradigm, different cost encoding,
  same optimal cost, weaker search performance on larger instances,
  and a genuine bug we found and diagnosed in the reference model).
- Worth highlighting in the video: the reference-model bug we found
  (Section "Performance optimizations", point 2) and the
  base-vs-extended symmetry-breaking pitfall (point 3) — both show
  hands-on verification, not just reading the models.
# talent_scheduling
