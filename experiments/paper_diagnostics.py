"""Author-source-verified one-step diagnostic; no training is repeated.

The mathematical definition is verified against the supplied author Fortran/R
sources; it is not a test of full dynamic Nash equilibrium. Existing training
records and source manifests are read without modification.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from collusion.analysis import evaluate_policy, policy_dynamics, reachable_cycle
from collusion.model import Game


TOLERANCE = 1e-8
DEFINITION = (
    "Author-source-confirmed one-step diagnostic: Qpolicy(s,a) = "
    "r(s,a,rival_policy(s)) + discount * Vpolicy(next_state). A single current "
    "action may change; all future actions follow frozen learned policies. "
    "Verified against author QL_routines::computeQCell and QGapToMaximum::"
    "computeQGapToMaxSession. The default author action flag uses exact max "
    "equality; a separate 1e-8-tolerance flag is retained. Table I's label "
    "'All States' actually reads QGapNotOnPath (off-path) in table_I.R. "
    "This is not a test of full dynamic Nash equilibrium."
)

AUTHOR_FILES = (
    "vendor/calvano_original/AER_fcode/baseline/QL_routines.f90",
    "vendor/calvano_original/AER_fcode/baseline/QGapToMaximum.f90",
    "vendor/calvano_original/AER_fcode/baseline/EquilibriumCheck.f90",
    "vendor/calvano_original/AER_fcode/baseline/DetailedAnalysis.f90",
    "vendor/calvano_original/AER_paper_Rscripts/table_I/table_I.R",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def author_q_cell_reference(game, policy, initial_state, price, player):
    """Literal algorithmic translation of baseline computeQCell for audit tests.

    It records states *after* each action and includes the first cycle visit in
    the prefix, exactly as in the author routine. The production diagnostic
    uses an equivalent shared policy-value calculation for efficiency.
    """
    policy = np.asarray(policy)
    action = policy[:, initial_state].copy()
    action[player] = price
    visited, positions, rewards = [], {}, []
    for _ in range(game.states+2):
        joint = int(sum(int(action[i])*game.m**(game.n-1-i) for i in range(game.n)))
        state = joint if game.k else 0
        rewards.append(game.rewards[joint, player])
        visited.append(state)
        if state in positions:
            prefix_length = positions[state]+1
            cycle_length = len(visited)-prefix_length
            prefix = np.sum(game.discount**np.arange(prefix_length)*rewards[:prefix_length])
            tail = np.sum(game.discount**np.arange(cycle_length)*rewards[prefix_length:])
            return float(prefix+game.discount**prefix_length*tail/(1-game.discount**cycle_length))
        positions[state] = len(visited)-1
        action = policy[:, state]
    raise RuntimeError("Author QCell cycle detection unexpectedly failed")


def one_step_diagnostic(game, policy, final_state):
    """Return phase-averaged one-step losses, separate from complete BR losses."""
    if game.n != 2:
        raise ValueError("Paper one-step diagnostic is restricted to two firms")
    policy = np.asarray(policy, dtype=np.int64)
    joint, successor, rewards = policy_dynamics(game, policy)
    _, cycle = reachable_cycle(successor, final_state)
    values = evaluate_policy(successor, rewards, game.discount)
    on_path, all_states, off_path, player_flags, author_flags, gaps = [], [], [], [], [], []
    off_mask = np.ones(game.states, dtype=bool)
    off_mask[cycle] = False
    for player in range(game.n):
        weight = game.m ** (game.n - 1 - player)
        candidate = joint[:, None] + weight * (
            np.arange(game.m)[None, :] - policy[player, :, None])
        next_state = candidate if game.k else np.zeros_like(candidate)
        q_policy = game.rewards[candidate, player] + game.discount * values[next_state, player]
        maximum = q_policy.max(axis=1)
        chosen = q_policy[np.arange(game.states), policy[player]]
        advantage = np.maximum(maximum - chosen, 0.0)
        loss = np.divide(advantage, np.abs(maximum), out=np.zeros_like(advantage),
                         where=np.abs(maximum) > 1e-15)
        on_path.append(float(loss[cycle].mean()))
        all_states.append(float(loss.mean()))
        off_path.append(float(loss[off_mask].mean()) if off_mask.any() else None)
        player_flags.append(bool(np.all(advantage[cycle] <= TOLERANCE)))
        author_flags.append(bool(np.all(chosen[cycle] == maximum[cycle])))
        gaps.append(float(advantage[cycle].max()))
    return dict(paper_one_step_loss_on_path=float(np.mean(on_path)),
                paper_one_step_loss_all_states=float(np.mean(all_states)),
                paper_one_step_loss_off_path=float(np.mean(off_path)) if off_mask.any() else None,
                paper_one_step_no_profitable_deviation=bool(all(player_flags)),
                author_one_step_no_profitable_deviation=bool(all(author_flags)),
                author_one_step_player_on_path_flags=author_flags,
                paper_one_step_player_on_path_flags=player_flags,
                paper_one_step_loss_on_path_by_player=on_path,
                paper_one_step_loss_all_states_by_player=all_states,
                paper_one_step_loss_off_path_by_player=off_path,
                paper_one_step_max_advantage_on_path_by_player=gaps,
                cycle_length=len(cycle), optimality_tolerance=TOLERANCE)


def summarize_diagnostics(records):
    valid = [row for row in records if row["converged"]]
    summary = dict(sessions=len(records), converged=len(valid), censored=len(records)-len(valid))
    if not valid:
        return summary
    for field in ("paper_one_step_loss_on_path", "paper_one_step_loss_all_states", "paper_one_step_loss_off_path"):
        values = np.asarray([row[field] for row in valid if row.get(field) is not None])
        if not len(values):
            continue
        summary[field] = float(values.mean())
        summary[f"{field}_std"] = float(values.std(ddof=1)) if len(values) > 1 else None
    summary["paper_one_step_no_profitable_deviation_frequency"] = float(np.mean([
        row["paper_one_step_no_profitable_deviation"] for row in valid]))
    if all("author_one_step_no_profitable_deviation" in row for row in valid):
        summary["author_one_step_no_profitable_deviation_frequency"] = float(np.mean([
            row["author_one_step_no_profitable_deviation"] for row in valid]))
    if all("full_dynamic_equilibrium" in row for row in valid):
        summary["full_dynamic_equilibrium_frequency"] = float(np.mean([
            row["full_dynamic_equilibrium"] for row in valid]))
        summary["full_dynamic_value_loss_on_path"] = float(np.mean([
            row["full_dynamic_value_loss_on_path"] for row in valid]))
    return summary


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value) if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})


def plot_comparison(output, summaries, specs):
    """Show the two distinct tests on the reduced parameter grid."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    grid = [(spec, summaries[spec["name"]]) for spec in specs
            if spec["name"] in summaries and
            (spec["name"] == "baseline" or spec["name"].startswith("grid_")) and
            "paper_one_step_no_profitable_deviation_frequency" in summaries[spec["name"]]]
    if len(grid) < 2:
        return None
    alphas = sorted({spec["alpha"] for spec, _ in grid})
    betas = sorted({spec["beta"] for spec, _ in grid})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    metrics = ("author_one_step_no_profitable_deviation_frequency", "full_dynamic_equilibrium_frequency")
    titles = ("Author one-step no-deviation test\n(confirmed source definition)",
              "Full dynamic best-response test\n(on-path Nash equilibrium)")
    for ax, metric, title in zip(axes, metrics, titles):
        matrix = np.full((len(alphas), len(betas)), np.nan)
        for spec, summary in grid:
            matrix[alphas.index(spec["alpha"]), betas.index(spec["beta"])]=summary[metric]
        plot = ax.imshow(matrix, origin="lower", aspect="auto", vmin=0, vmax=1, cmap="viridis")
        ax.set_xticks(range(len(betas)), [f"{b*1e5:g}" for b in betas])
        ax.set_yticks(range(len(alphas)), [f"{a:g}" for a in alphas])
        ax.set(xlabel="beta x 1e5", ylabel="alpha", title=title)
        for spec, summary in grid:
            ax.text(betas.index(spec["beta"]), alphas.index(spec["alpha"]),
                    f"{summary[metric]:.3f}\nn={summary['converged']}",
                    ha="center", va="center", fontsize=9, color="white")
        fig.colorbar(plot, ax=ax, fraction=.045)
    fig.suptitle("Author one-step test versus full dynamic response; reduced grid only", fontsize=11)
    fig.tight_layout()
    path = output / "figures" / "figure2_one_step_vs_dynamic.png"
    path.parent.mkdir(exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def build_diagnostics(output):
    output = Path(output)
    train_manifest = output / "manifest.json"
    manifest = json.loads(train_manifest.read_text(encoding="utf-8"))
    # Refuse to evaluate frozen snapshots with a different game/value evaluator.
    for relative, expected in manifest["source_sha256"].items():
        normalized = relative.replace("\\", "/")
        if normalized in ("src/collusion/model.py", "src/collusion/analysis.py"):
            if sha256(ROOT / normalized) != expected:
                raise RuntimeError(f"Diagnostic dependency differs from training source: {relative}")
    summaries, session_rows, inputs = {}, [], {}
    for spec in manifest["config"]["scenarios"]:
        parameters = spec.get("game", {})
        if len(parameters.get("costs", (1, 1))) != 2:
            continue
        directory = output / spec["name"]
        paths = sorted(directory.glob("session_*.json"))
        if not paths:
            continue
        game, rows = Game(**parameters), []
        for path in paths:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["signature"] != manifest["identity"]:
                raise RuntimeError(f"Training identity mismatch: {path}")
            snapshot = directory / record["snapshot"]
            actual_hash = sha256(snapshot)
            if actual_hash != record["snapshot_sha256"]:
                raise RuntimeError(f"Snapshot integrity check failed: {snapshot}")
            with np.load(snapshot, allow_pickle=False) as data:
                diagnosis = one_step_diagnostic(game, data["policy"], int(data["final_state"]))
            row = dict(scenario=spec["name"], index=record["index"], seed=record["seed"],
                       converged=record["converged"], mean_delta=record["mean_delta"],
                       cycle_class=record["cycle_class"], **diagnosis,
                       full_dynamic_value_loss_on_path=record["q_loss_on_path"],
                       full_dynamic_value_loss_all_states=record["q_loss_all_states"],
                       full_dynamic_equilibrium=record["is_equilibrium"],
                       snapshot=str(snapshot.relative_to(output)), snapshot_sha256=actual_hash)
            rows.append(row)
            inputs[str(path.relative_to(output))] = sha256(path)
        session_rows.extend(rows)
        summaries[spec["name"]] = summarize_diagnostics(rows)
    comparisons = []
    baseline = summaries.get("baseline", {})
    for metric, reference in (("paper_one_step_loss_on_path", .002),
                              ("paper_one_step_loss_off_path", .018),
                              ("author_one_step_no_profitable_deviation_frequency", .505)):
        if metric not in baseline:
            continue
        actual = baseline[metric]
        comparisons.append(dict(metric=metric, paper=reference, reproduced=actual,
                                signed_error=actual-reference, absolute_error=abs(actual-reference),
                                relative_error=abs(actual-reference)/reference,
                                source="Table 1, All column, p.3277",
                                author_definition_verified=True,
                                caveat=("Table I label All States reads QGapNotOnPath (off-path); "
                                        "author flag exact max equality; not full dynamic Nash test")))
    tables = output / "tables"
    tables.mkdir(exist_ok=True)
    write_csv(tables / "paper_one_step_sessions.csv", session_rows)
    write_csv(tables / "paper_one_step_comparison.csv", comparisons)
    baseline_rows = [row for row in session_rows if row["scenario"] == "baseline" and row["converged"]]
    grouped = []
    for label in ("1-Sym.", "1-Asym.", "1", "2", ">=3", "All", "Author-one-step"):
        subset = [row for row in baseline_rows if label == "All" or
                  (label == "1" and row["cycle_length"] == 1) or
                  (label == "Author-one-step" and row["author_one_step_no_profitable_deviation"]) or
                  row["cycle_class"] == label]
        if not subset:
            continue
        delta = np.asarray([row["mean_delta"] for row in subset])
        grouped.append(dict(group=label, frequency=len(subset)/len(baseline_rows),
                            mean_delta=float(delta.mean()),
                            std_delta=float(delta.std(ddof=1)) if len(delta)>1 else None,
                            **summarize_diagnostics(subset)))
    write_csv(tables / "table1_author_one_step.csv", grouped)
    diagnostic = dict(definition=DEFINITION, loss_unit="fraction (0.002 = 0.2 percent)",
                      sample="Only converged sessions enter scenario means; all sessions retained in CSV",
                      author_sources_sha256={name:sha256(ROOT/name) for name in AUTHOR_FILES},
                      author_flag_tolerance=0.0, supplementary_flag_tolerance=TOLERANCE,
                      source_train_identity=manifest["identity"], scenarios=summaries)
    (output / "paper_diagnostics.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    comparison_plot = plot_comparison(output, summaries, manifest["config"]["scenarios"])
    outputs = [tables / "paper_one_step_sessions.csv", tables / "paper_one_step_comparison.csv",
               tables / "table1_author_one_step.csv", output / "paper_diagnostics.json"]
    if comparison_plot:
        outputs.append(comparison_plot)
    evidence = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                    script="experiments/paper_diagnostics.py", script_sha256=sha256(__file__),
                    source_train_identity=manifest["identity"],
                    source_train_manifest_sha256=sha256(train_manifest),
                    source_dependencies={name: sha256(ROOT / name) for name in
                                         ("src/collusion/model.py", "src/collusion/analysis.py")},
                    input_record_sha256=inputs,
                    outputs_sha256={str(path.relative_to(output)): sha256(path) for path in outputs if path.exists()})
    (output / "diagnostics_manifest.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return diagnostic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/validated")
    args = parser.parse_args()
    diagnostic = build_diagnostics(ROOT / args.output)
    print(json.dumps(diagnostic, indent=2))


if __name__ == "__main__":
    main()
