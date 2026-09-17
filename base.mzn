% =====================================================================
% Talent Scheduling Problem (CSPLib prob039) - Base model 
% =====================================================================

include "globals.mzn";

int: numScenes;
int: numActors;

set of int: Scenes = 1..numScenes;
set of int: Actors = 1..numActors;

array[Actors, Scenes] of 0..1: ia;
array[Scenes] of int: d;
array[Actors] of int: c;

array[Scenes] of var Scenes: seq;
constraint all_different(seq);

array[0..numScenes] of var int: cumDur;
constraint cumDur[0] = 0;
constraint forall(i in 1..numScenes)(
    cumDur[i] = cumDur[i-1] + d[seq[i]]
);

array[Actors, Scenes] of var 0..1: presentAt;
constraint forall(a in Actors, i in Scenes)(
    presentAt[a,i] = ia[a, seq[i]]
);

array[Actors] of var 1..numScenes: firstSlot;
array[Actors] of var 1..numScenes: lastSlot;
constraint forall(a in Actors)(
    firstSlot[a] = min([ if presentAt[a,i] = 1 then i else numScenes+1 endif | i in Scenes ])
    /\
    lastSlot[a]  = max([ if presentAt[a,i] = 1 then i else 0 endif | i in Scenes ])
);

array[Actors] of var int: actorCost;
constraint forall(a in Actors)(
    actorCost[a] = c[a] * (cumDur[lastSlot[a]] - cumDur[firstSlot[a]-1])
);

var int: totalCost = sum(a in Actors)(actorCost[a]);

% -------------------- Added optimizations --------------------------
% number of scenes each actor appears in (fixed data, computable up front)
array[Actors] of int: nAppear = [ sum(i in Scenes)(ia[a,i]) | a in Actors ];

% redundant/implied constraint (Barbara Smith): an actor's span can never
% be shorter than (appearances - 1) scenes
constraint forall(a in Actors)(
    lastSlot[a] - firstSlot[a] >= nAppear[a] - 1
);

% symmetry breaking: schedule and its mirror are equally good, so we
% break the reflection symmetry by fixing an ordering on the endpoints
constraint seq[1] < seq[numScenes];

solve :: int_search(seq, first_fail, indomain_min, complete)
    minimize totalCost;

output [
  "ORDER=", show(seq), "\n",
  "FIRSTSLOT=", show(firstSlot), "\n",
  "LASTSLOT=", show(lastSlot), "\n",
  "ACTORCOST=", show(actorCost), "\n",
  "TOTALCOST=", show(totalCost), "\n"
];
