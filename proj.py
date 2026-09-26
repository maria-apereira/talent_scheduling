#!/usr/bin/env python3
"""
proj.py - Talent Scheduling Problem (CSPLib prob039) + location/travel extension

Pipeline:
  1. Read a problem instance from a JSON file.
  2. Encode it as a MiniZinc .dzn data file.
  3. Invoke the MiniZinc solver on the chosen model (base or extended).
  4. Parse the solver's output and print a human-readable schedule
     to standard output.

Usage:
    python3 proj.py --instance data/example.json --model extended
    python3 proj.py --instance data/example.json --model base
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"


# --------------------------------------------------------------------
# Step 1: read the instance
# --------------------------------------------------------------------
def load_instance(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


# --------------------------------------------------------------------
# Step 2: encode as MiniZinc .dzn
# --------------------------------------------------------------------
def dzn_array2d(name: str, rows) -> str:
    body = "|".join(", ".join(str(v) for v in row) for row in rows)
    return f"{name} = [| {body} |];"


def dzn_array1d(name: str, values) -> str:
    return f"{name} = [{', '.join(str(v) for v in values)}];"


def encode_dzn(instance: dict, model: str) -> str:
    lines = [
        f"numScenes = {instance['numScenes']};",
        f"numActors = {instance['numActors']};",
        dzn_array2d("ia", instance["ia"]),
        dzn_array1d("d", instance["d"]),
        dzn_array1d("c", instance["c"]),
    ]
    if model == "extended":
        lines.append(f"numLocations = {instance['numLocations']};")
        lines.append(dzn_array1d("loc", instance["loc"]))
        lines.append(dzn_array2d("travel", instance["travel"]))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------
# Step 3: invoke MiniZinc
# --------------------------------------------------------------------
def run_minizinc(model_path: Path, dzn_path: Path, solver: str = "chuffed",
                 time_limit: int = 60, std_globals: bool = False):
    """Run MiniZinc; returns (stdout, proved_optimal).

    On timeout MiniZinc still prints the best solution found so far but
    omits the '==========' optimality marker.
    """
    cmd = ["minizinc", "--solver", solver, "--time-limit", str(time_limit * 1000)]
    if std_globals:
        # Works around a packaging mismatch on some apt installs where a
        # solver's bundled globals are out of sync with the std library.
        cmd += ["-G", "std"]
    cmd += [str(model_path), str(dzn_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("MiniZinc failed:", result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout, "==========" in result.stdout


# --------------------------------------------------------------------
# Step 4: parse solver output
# --------------------------------------------------------------------
def parse_int_list(raw: str):
    return [int(x) for x in re.findall(r"-?\d+", raw)]


def parse_output(raw: str) -> dict:
    fields = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in ("ORDER", "LOCATIONS", "FIRSTSLOT", "LASTSLOT", "ACTORCOST"):
            fields[key] = parse_int_list(value)
        elif key in ("TOTALCOST", "TOTAL_ACTOR_COST", "TOTAL_TRAVEL_COST"):
            match = re.search(r"-?\d+", value)
            if match:
                fields[key] = int(match.group())
    return fields


def compute_cost(instance: dict, model: str, order) -> tuple:
    """Recompute (actor_cost, travel_cost) of a schedule independently of the solver."""
    d, c, ia = instance["d"], instance["c"], instance["ia"]
    n = len(order)
    actor_cost = 0
    for a in range(len(c)):
        slots = [i for i, sc in enumerate(order) if ia[a][sc - 1]]
        if not slots:
            continue
        first, last = slots[0], slots[-1]
        idle = sum(d[order[i] - 1] for i in range(first, last + 1)
                   if not ia[a][order[i] - 1])
        actor_cost += c[a] * idle
    travel_cost = 0
    if model == "extended":
        loc, travel = instance["loc"], instance["travel"]
        travel_cost = sum(travel[loc[order[i] - 1] - 1][loc[order[i + 1] - 1] - 1]
                          for i in range(n - 1))
    return actor_cost, travel_cost


def print_schedule(instance: dict, model: str, fields: dict) -> None:
    order = fields.get("ORDER", [])
    print("=== Shooting schedule ===")
    for pos, scene in enumerate(order, start=1):
        line = f"Day slot {pos}: Scene {scene} (duration {instance['d'][scene-1]})"
        if model == "extended" and "LOCATIONS" in fields:
            line += f" @ location {fields['LOCATIONS'][pos-1]}"
        print(line)

    print("\n=== Cost breakdown ===")
    if "ACTORCOST" in fields:
        for a, cost in enumerate(fields["ACTORCOST"], start=1):
            print(f"Actor {a}: cost = {cost}")

    if model == "extended":
        print(f"Total actor cost:  {fields.get('TOTAL_ACTOR_COST')}")
        print(f"Total travel cost: {fields.get('TOTAL_TRAVEL_COST')}")
    print(f"TOTAL COST: {fields.get('TOTALCOST')}")


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Talent Scheduling solver pipeline")
    parser.add_argument("--instance", required=True, help="Path to instance JSON file")
    parser.add_argument(
        "--model", choices=["base", "extended"], default="extended",
        help="Which model to run (base = CSPLib prob039, extended = + locations/travel)"
    )
    parser.add_argument("--solver", default="chuffed",
                        help="MiniZinc solver to use (default: chuffed)")
    parser.add_argument("--time-limit", type=int, default=60,
                        help="Solver time limit in seconds (default: 60)")
    parser.add_argument("--std-globals", action="store_true",
                        help="Pass -G std to MiniZinc (only if you hit a globals type error)")
    parser.add_argument("--verbose", action="store_true",
                        help="Also print the raw solver output to stderr")
    args = parser.parse_args()

    instance = load_instance(args.instance)
    dzn_text = encode_dzn(instance, args.model)

    model_path = MODELS_DIR / f"{args.model}.mzn"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".dzn", delete=False) as tmp:
        tmp.write(dzn_text)
        dzn_path = Path(tmp.name)

    try:
        raw_output, optimal = run_minizinc(
            model_path, dzn_path, args.solver, args.time_limit, args.std_globals)
        if args.verbose:
            print(raw_output, file=sys.stderr)
        fields = parse_output(raw_output)
        if "ORDER" not in fields:
            print(f"No solution found within {args.time_limit}s "
                  "(or the instance is unsatisfiable).")
            sys.exit(2)
        print_schedule(instance, args.model, fields)
        actor, travel = compute_cost(instance, args.model, fields["ORDER"])
        ok = actor + travel == fields.get("TOTALCOST")
        print(f"Independent check: recomputed cost {actor + travel} "
              + ("matches the solver." if ok else "DOES NOT MATCH the solver!"))
        if not ok:
            sys.exit(3)
        print("Status: " + ("OPTIMAL (proved)" if optimal else
              f"best found within {args.time_limit}s (optimality not proved)"))
    finally:
        dzn_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
