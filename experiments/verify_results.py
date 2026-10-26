"""Check hashes, session completeness, saved policies, aggregates, and seeded reruns."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from collusion.model import Game
from collusion.learning import run_session
from collusion.analysis import analyze_session
from collusion.reporting import summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/validated")
    parser.add_argument("--rerun", type=int, default=3, help="Replay this many baseline seeds sequentially")
    args = parser.parse_args()
    folder = ROOT / args.output
    manifest = json.loads((folder / "manifest.json").read_text())
    config = manifest["config"]; settings = config["settings"]
    results = json.loads((folder / "summary.json").read_text())
    started = time.perf_counter()
    for name, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256((ROOT / name.replace("\\", "/")).read_bytes()).hexdigest()
        assert actual == expected, f"Source changed since run: {name}"
    checked, replayed = 0, 0
    for spec in config["scenarios"]:
        directory = folder / spec["name"]
        paths = sorted(directory.glob("session_*.json"))
        assert len(paths) == spec.get("sessions",settings["sessions"]), f"Incomplete: {spec['name']}"
        game = Game(**spec.get("game", {}))
        records = []
        for index,path in enumerate(paths):
            record = json.loads(path.read_text()); records.append(record)
            assert record["seed"] == settings["seed_start"]+index
            assert record["index"] == index and record["signature"] == manifest["identity"]
            assert record["steps"] <= settings["max_periods"]
            if record["converged"]: assert record["steps"] >= settings["stable_periods"]
            snapshot = directory / record["snapshot"]
            assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == record["snapshot_sha256"]
            with np.load(snapshot) as data:
                policy=data["policy"]; state=int(data["final_state"])
                assert policy.shape == (game.n,game.states) and state == record["final_state"]
                assert np.min(policy)>=0 and np.max(policy)<game.m
                actions = np.array(record["cycle_actions"])
                joint = actions @ (game.m**np.arange(game.n-1,-1,-1))
                profit = game.rewards[joint].mean(axis=0)
                np.testing.assert_allclose(profit,record["mean_profit"],rtol=0,atol=1e-13)
                delta=((profit-game.profit_nash)/(game.profit_monopoly-game.profit_nash)).mean()
                np.testing.assert_allclose(delta,record["mean_delta"],rtol=0,atol=1e-12)
                if spec["name"] == "baseline" and index < args.rerun:
                    actual=run_session(game,spec["alpha"],spec["beta"],record["seed"],
                                       stable_periods=settings["stable_periods"],max_periods=settings["max_periods"],sample_every=settings["sample_every"])
                    np.testing.assert_array_equal(actual[1],policy)
                    assert actual[2:5] == (state,record["steps"],record["converged"])
                    np.testing.assert_array_equal(actual[5],data["history"])
                    if "q" in data: np.testing.assert_array_equal(actual[0],data["q"])
                    diagnostic=analyze_session(game,policy,state)
                    for field in ("mean_delta","q_loss_on_path","q_loss_all_states"):
                        np.testing.assert_allclose(diagnostic[field],record[field],rtol=0,atol=1e-13)
                    replayed += 1
            checked += 1
        recomputed=summarize(records)
        for field,value in recomputed.items():
            np.testing.assert_allclose(value,results[spec["name"]][field],rtol=0,atol=1e-12)
    evidence=dict(status="passed",sessions_checked=checked,seeded_baseline_reruns=replayed,
                  exact_policy_history_q_replay=True if replayed else None,sha256_verified=True,
                  source_sha256_verified=True,aggregate_recomputed=True,
                  elapsed_seconds=time.perf_counter()-started)
    (folder / "verification.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    print(json.dumps(evidence,indent=2))


if __name__ == "__main__":
    main()
