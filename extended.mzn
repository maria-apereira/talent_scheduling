% =====================================================================
% Talent Scheduling Problem - EXTENDED model 
% =====================================================================

include "globals.mzn";

int: numScenes;
int: numActors;
int: numLocations;

set of int: Scenes = 1..numScenes;
set of int: Actors = 1..numActors;
set of int: Locations = 1..numLocations;

array[Actors, Scenes] of 0..1: ia;
array[Scenes] of int: d;
array[Actors] of int: c;

array[Scenes] of Locations: loc;
array[Locations, Locations] of int: travel;

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

var int: totalActorCost = sum(a in Actors)(actorCost[a]);

array[Scenes] of var Locations: locAt;
constraint forall(i in Scenes)(
    locAt[i] = loc[seq[i]]
);

array[1..numScenes-1] of var int: travelCost;
constraint forall(i in 1..numScenes-1)(
    travelCost[i] = travel[locAt[i], locAt[i+1]]
);

var int: totalTravelCost = sum(i in 1..numScenes-1)(travelCost[i]);

var int: totalCost = totalActorCost + totalTravelCost;

% -------------------- Added optimizations --------------------------
array[Actors] of int: nAppear = [ sum(i in Scenes)(ia[a,i]) | a in Actors ];
constraint forall(a in Actors)(
    lastSlot[a] - firstSlot[a] >= nAppear[a] - 1
);


solve :: int_search(seq, first_fail, indomain_min, complete)
    minimize totalCost;

output [
  "ORDER=", show(seq), "\n",
  "LOCATIONS=", show(locAt), "\n",
  "FIRSTSLOT=", show(firstSlot), "\n",
  "LASTSLOT=", show(lastSlot), "\n",
  "ACTORCOST=", show(actorCost), "\n",
  "TOTAL_ACTOR_COST=", show(totalActorCost), "\n",
  "TOTAL_TRAVEL_COST=", show(totalTravelCost), "\n",
  "TOTALCOST=", show(totalCost), "\n"
];
