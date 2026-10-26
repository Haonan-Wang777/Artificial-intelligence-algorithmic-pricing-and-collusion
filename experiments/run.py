"""Reproducible experiment entry point; each session is an independently seeded job."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(key, "1")
import numpy as np
from collusion.model import Game
from collusion.learning import run_session

_games = {}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def worker(task):
    from collusion.analysis import analyze_session, impulse_response
    spec, settings, index, directory, signature = task
    directory = Path(directory)
    record_path = directory / f"session_{index:05d}.json"
    if record_path.exists():
        record = json.loads(record_path.read_text())
        if record.get("signature") == signature and (directory / record["snapshot"]).exists():
            actual = hashlib.sha256((directory / record["snapshot"]).read_bytes()).hexdigest()
            if actual != record["snapshot_sha256"]:
                raise RuntimeError(f"Snapshot integrity check failed: {record_path}")
            return record
        raise RuntimeError(f"Refusing to mix incompatible runs in {directory}")
    game_key = digest(spec.get("game", {}))
    if game_key not in _games:
        _games[game_key] = Game(**spec.get("game", {}))
    game = _games[game_key]
    seed = settings["seed_start"] + index
    start = time.perf_counter()
    q, policy, state, steps, converged, history = run_session(
        game, spec["alpha"], spec["beta"], seed,
        stable_periods=settings["stable_periods"], max_periods=settings["max_periods"],
        sample_every=settings["sample_every"])
    record = dict(index=index, seed=seed, signature=signature, steps=int(steps),
                  converged=bool(converged), final_state=int(state),
                  elapsed_seconds=time.perf_counter()-start,
                  snapshot=f"session_{index:05d}.npz")
    # Terminal policy diagnostics are retained for censored runs but excluded from primary summaries.
    record.update(analyze_session(game, policy, state))
    if game.n == 2 and game.shock == 0:
        record["impulse"] = impulse_response(game, policy, state)
    values = dict(policy=policy, final_state=np.array(state), history=history)
    if index < settings.get("save_q_first", 5):
        values["q"] = q
    np.savez_compressed(directory / record["snapshot"], **values)
    record["snapshot_sha256"] = hashlib.sha256((directory / record["snapshot"]).read_bytes()).hexdigest()
    temporary = record_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
    temporary.replace(record_path)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/validated.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--only", nargs="*", help="Optional scenario names")
    args = parser.parse_args()
    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    output = ROOT / (args.output or f"results/{config['name']}")
    output.mkdir(parents=True, exist_ok=True)
    settings = config["settings"]
    sources = sorted((ROOT / "src/collusion").glob("*.py")) + [Path(__file__).resolve()]
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    metadata = dict(config=config, python=sys.version, platform=platform.platform(),
                    numpy=np.__version__, source_sha256=hashes,
                    started_utc=datetime.now(timezone.utc).isoformat(), command=sys.argv)
    import scipy, numba
    metadata.update(scipy=scipy.__version__, numba=numba.__version__)
    identity = digest(dict(config=config, source_sha256=hashes,
                           environment={k:metadata[k] for k in ("python","numpy","scipy","numba")}))
    manifest = output / "manifest.json"
    if manifest.exists() and json.loads(manifest.read_text())["identity"] != identity:
        raise RuntimeError("Output manifest differs: choose a fresh --output folder")
    if not manifest.exists():
        manifest.write_text(json.dumps(dict(identity=identity, **metadata), indent=2), encoding="utf-8")
    for spec in config["scenarios"]:
        if args.only and spec["name"] not in args.only:
            continue
        directory = output / spec["name"]
        directory.mkdir(exist_ok=True)
        sessions = spec.get("sessions", settings["sessions"])
        tasks = [(spec, settings, i, str(directory), identity) for i in range(sessions)]
        begin = time.perf_counter()
        if args.workers == 1:
            iterator = map(worker, tasks)
            for i, record in enumerate(iterator, 1):
                if i == 1 or i % 25 == 0 or i == sessions:
                    print(f"{spec['name']}: {i}/{sessions}; last steps={record['steps']}; elapsed={time.perf_counter()-begin:.1f}s", flush=True)
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                for i, record in enumerate(pool.map(worker, tasks, chunksize=1), 1):
                    if i == 1 or i % 25 == 0 or i == sessions:
                        print(f"{spec['name']}: {i}/{sessions}; last steps={record['steps']}; elapsed={time.perf_counter()-begin:.1f}s", flush=True)
    from collusion.reporting import build_results
    build_results(output)
    print(f"Finished: {output}", flush=True)


if __name__ == "__main__":
    main()
