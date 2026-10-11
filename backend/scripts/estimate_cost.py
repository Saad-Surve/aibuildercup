"""Recalculate explicit workflow component scenarios; no network or provider calls."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "evals/cost-scenario.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text())
    rows = []
    total = Decimal(0)
    for component in scenario["components"]:
        quantity = Decimal(str(component["quantity"]))
        rate = Decimal(str(component["usd_per_unit"]))
        if not quantity.is_finite() or not rate.is_finite() or quantity < 0 or rate < 0:
            raise ValueError("Quantities and rates must be finite and nonnegative")
        cost = quantity * rate
        total += cost
        rows.append({**component, "estimated_usd": float(cost)})
    result = {
        **scenario,
        "scenario_sha256": hashlib.sha256(args.scenario.read_bytes()).hexdigest(),
        "components": rows,
        "component_subtotal_usd": float(total),
        "scope": "partial subtotal excluding every category listed in excluded",
    }
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
