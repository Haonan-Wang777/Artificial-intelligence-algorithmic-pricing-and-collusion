"""Write the 100 x 100 x 1000 paper-scale plan without starting expensive work."""
import argparse
import json
from pathlib import Path
import numpy as np

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="configs/paper_full.json")
    args = parser.parse_args()
    scenarios = []
    # beta=0 excluded: 100 positive equally spaced values, smallest 2e-7.
    for i, alpha in enumerate(np.linspace(.025, .25, 100)):
        for j, beta in enumerate(np.linspace(2e-7, 2e-5, 100)):
            scenarios.append(dict(name=f"a{i:03d}_b{j:03d}", alpha=float(alpha), beta=float(beta), game={}))
    config = dict(name="paper_full", description="10 million sessions; very expensive, not executed in this delivery.",
                  settings=dict(sessions=1000, seed_start=20261023, stable_periods=100000,
                                max_periods=1000000000, sample_every=1000000, save_q_first=0),
                  scenarios=scenarios)
    Path(args.output).write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Wrote {len(scenarios)} parameter points to {args.output}; no training started.")
