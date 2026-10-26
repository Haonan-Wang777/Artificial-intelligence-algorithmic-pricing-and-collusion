"""Audit and summarize outputs of the unmodified official baseline executable.

Native gain/equilibrium fields are retained as authoritative executable results.
Table I losses are recomputed from saved original strategies using the verified
one-period-deviation definition, including zero-loss sessions. The unrelated
positive-only outer A_qg aggregation is deliberately not substituted for Table I.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
from scipy.stats import t as student_t

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from collusion.analysis import policy_dynamics, reachable_cycle
from paper_diagnostics import one_step_diagnostic, sha256, write_csv


def read_native_table(path):
    """Read the whitespace header and one experiment, preserving numeric text."""
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 2:
        raise ValueError(f"Expected exactly one experiment in {path}")
    headers, cells = lines[0].split(), lines[1].split()
    if len(headers) != len(cells):
        raise ValueError(f"Native output column mismatch in {path}: {len(headers)} vs {len(cells)}")
    result = {}
    for name, value in zip(headers, cells):
        try:
            parsed = float(value.replace("D", "E"))
        except ValueError:
            parsed = value
        if name not in result:
            result[name] = parsed
    return result


def read_original_input(path):
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    def setting(label):
        return int(lines[lines.index(label)+1])
    model_at = next(i for i, line in enumerate(lines) if line.startswith("Model"))
    model = dict(zip(lines[model_at].split(), lines[model_at+1].split()))
    return dict(sessions=setting("Number of sessions"),
                cores=setting("Number of cores"),
                agents=setting("Number of Agents:"), memory=setting("Memory:"),
                prices=setting("Number of Prices:"),
                iterations_per_episode=setting("Iterations per episode"),
                max_episodes=setting("Maximum number of episode"), model=model)


def reconstruct_original_game(settings):
    """Match PI_routines' input prices, sequential grid addition and raw logit.

    The author input contains five-decimal Nash/monopoly prices. Re-solving the
    continuous benchmarks would subtly change both prices and the profit table.
    """
    if settings["agents"] != 2 or settings["memory"] not in (0, 1):
        raise ValueError("This audit targets the original two-firm baseline")
    model = settings["model"]
    n, m = settings["agents"], settings["prices"]
    price_nash = np.array([float(model[f"NashP{i+1}"]) for i in range(n)])
    price_monopoly = np.array([float(model[f"CoopP{i+1}"]) for i in range(n)])
    quality = np.array([float(model[f"a{i+1}"]) for i in range(n)])
    costs = np.array([float(model[f"c{i+1}"]) for i in range(n)])
    outside, mu = float(model["a0"]), float(model["mu"])
    lower, upper = float(model["extend1"]), float(model["extend2"])
    prices = np.empty((n, m))
    prices[:, 0] = price_nash-lower*(price_monopoly-price_nash)
    prices[:, -1] = price_monopoly+upper*(price_monopoly-price_nash)
    step = (prices[:, -1]-prices[:, 0])/(m-1)
    for index in range(1, m-1):
        prices[:, index] = prices[:, index-1]+step
    def profits(p):
        shares = np.exp((quality-p)/mu)
        shares = shares/(shares.sum()+np.exp(outside/mu))
        return (p-costs)*shares
    profiles = np.array([(i, j) for i in range(m) for j in range(m)], dtype=np.int64)
    rewards = np.array([profits(prices[np.arange(n), profile]) for profile in profiles])
    return SimpleNamespace(n=n, m=m, k=settings["memory"], states=m**n if settings["memory"] else 1,
                           prices=prices, profiles=profiles, rewards=rewards,
                           discount=float(model["Delta"]),
                           price_nash=price_nash, price_monopoly=price_monopoly,
                           profit_nash=profits(price_nash), profit_monopoly=profits(price_monopoly))


def read_original_sessions(path, game, expected_sessions):
    """Read ConvergenceResults::WRITE(999,9961), converting 1-based indexes.

    Prices/profits are printed agent-major, strategy rows are state-major. Saved
    cycle states describe the contemporaneous profile, while policy(state)
    produces the next cycle phase. All original text remains unmodified.
    """
    with Path(path).open(encoding="utf-8") as stream:
        def row():
            while True:
                line = stream.readline()
                if not line:
                    raise EOFError("Unexpected end of official InfoExperiment file")
                if line.strip():
                    return line.split()
        for expected in range(1, expected_sessions+1):
            session = int(row()[0])
            if session != expected:
                raise ValueError(f"Session ordering mismatch: {session} != {expected}")
            converged = bool(int(row()[0]))
            episodes = float(row()[0])
            length = int(row()[0])
            cycle_states = np.array(row(), dtype=np.int64)-1
            cycle_actions = np.array(row(), dtype=np.int64).reshape(game.n, length).T-1
            printed_profits = np.array(row(), dtype=float).reshape(game.n, length).T
            policy = np.array([row() for _ in range(game.states)], dtype=np.int64).T-1
            if len(cycle_states) != length or policy.shape != (game.n, game.states):
                raise ValueError(f"Malformed official session {session}")
            if np.any(policy < 0) or np.any(policy >= game.m):
                raise ValueError(f"Invalid saved action in session {session}")
            yield dict(session=session, converged=converged, episodes=episodes,
                       cycle_states=cycle_states, cycle_actions=cycle_actions,
                       printed_profits=printed_profits, policy=policy)
        if any(line.strip() for line in stream):
            raise ValueError("Unexpected trailing session data")


def native_impulse_figure(output, native):
    """Plot native aggregate means only; the executable's 'se' fields are SDs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if "AggrPricePre" not in native:
        return None
    rows = [dict(time=0, deviator_price=native["AggrPricePre"], opponent_price=native["AggrPricePre"])]
    for time in range(1, 16):
        rows.append(dict(time=time,
                         deviator_price=native[f"AggrDevPriceShockPer{time:03d}"],
                         opponent_price=native[f"AggrNonDevPriceShockPer{time:03d}"]))
    write_csv(output / "tables" / "figure4_original.csv", rows)
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    for field, label, color, marker in (("deviator_price", "Deviating agent", "#bd593e", "s"),
                                         ("opponent_price", "Other agent", "#187d8e", "o")):
        ax.plot([row["time"] for row in rows], [row[field] for row in rows],
                label=label, color=color, marker=marker, markersize=4)
    for value, label, style in ((native["NashPrice1"], "Nash benchmark", ":"),
                                 (native["CoopPrice1"], "Monopoly benchmark", "--"),
                                 (native["AggrPricePre"], "Long-run mean", "-.")):
        ax.axhline(value, label=label, linestyle=style, color="gray", linewidth=1)
    ax.set(xlabel="Time (one-period static best response at t=1)", ylabel="Price",
           title="Figure 4: unmodified author executable, 1,000 sessions")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    path = output / "figures" / "figure4_original.png"
    path.parent.mkdir(exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def compare_original_prefix(smoke_directory, baseline_directory, game, baseline_sessions):
    """Check unchanged seeded trajectories when increasing the session count."""
    smoke_directory, baseline_directory = Path(smoke_directory), Path(baseline_directory)
    if not (smoke_directory/"InfoExperiment_1.txt").exists():
        return dict(available=False, reason="Separate original smoke run was not supplied")
    smoke_settings = read_original_input(smoke_directory/"A_InputParameters.txt")
    smoke = read_original_sessions(smoke_directory/"InfoExperiment_1.txt", game, smoke_settings["sessions"])
    baseline = read_original_sessions(baseline_directory/"InfoExperiment_1.txt", game, baseline_sessions)
    comparisons = []
    for left, right in zip(smoke, baseline):
        if len(comparisons) >= 2:
            break
        equal = {field: bool(np.array_equal(left[field], right[field])) for field in
                 ("policy", "cycle_states", "cycle_actions", "printed_profits")}
        equal["episodes"] = left["episodes"] == right["episodes"]
        equal["converged"] = left["converged"] == right["converged"]
        comparisons.append(dict(session=left["session"], all_equal=all(equal.values()), checks=equal))
    result = dict(available=True, compared_sessions=len(comparisons),
                  all_equal=all(item["all_equal"] for item in comparisons), sessions=comparisons,
                  smoke_info_sha256=sha256(smoke_directory/"InfoExperiment_1.txt"),
                  baseline_info_sha256=sha256(baseline_directory/"InfoExperiment_1.txt"))
    if (smoke_directory/"execution.json").exists() and (baseline_directory/"execution.json").exists():
        result["smoke_cores"] = json.loads((smoke_directory/"execution.json").read_text()).get("cores", smoke_settings["cores"])
        result["baseline_cores"] = json.loads((baseline_directory/"execution.json").read_text()).get(
            "cores", read_original_input(baseline_directory/"A_InputParameters.txt")["cores"])
    if not result["all_equal"]:
        raise RuntimeError("Original two-session and 1000-session seeded prefix differ")
    return result


def summarize_original(output):
    output = Path(output)
    execution_path = output / "execution.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    if execution["status"] != "success" or execution["returncode"] != 0:
        raise RuntimeError("Original executable did not finish successfully")
    for name, expected in execution["outputs_sha256"].items():
        if sha256(output/name) != expected:
            raise RuntimeError(f"Native output hash mismatch: {name}")
    executable = output/"baseline.exe"
    if not executable.exists():
        executable = ROOT/"vendor/calvano_original/AER_fcode/baseline/baseline.exe"
    if sha256(executable) != execution["executable_sha256"]:
        raise RuntimeError("Original executable hash mismatch")
    settings = read_original_input(output / "A_InputParameters.txt")
    game = reconstruct_original_game(settings)
    native_conv = read_native_table(output / "A_convResults.txt")
    native_eq = read_native_table(output / "A_ec.txt")
    rows, max_print_error = [], 0.
    for session in read_original_sessions(output/"InfoExperiment_1.txt", game, settings["sessions"]):
        policy, states, length = session["policy"], session["cycle_states"], len(session["cycle_states"])
        joint, successor, _ = policy_dynamics(game, policy)
        _, detected = reachable_cycle(successor, int(states[0]))
        if set(detected) != set(states) or len(detected) != length:
            raise ValueError(f"Saved cycle and policy disagree in session {session['session']}")
        encoded_actions = session["cycle_actions"] @ np.array([game.m, 1])
        if not np.array_equal(encoded_actions, states):
            raise ValueError("Official price/action memory interpretation mismatch")
        if not np.array_equal(successor[states], np.roll(states, -1)):
            raise ValueError("Official state transition orientation mismatch")
        exact_profits = game.rewards[states]
        error = float(np.max(np.abs(exact_profits-session["printed_profits"])))
        max_print_error = max(error, max_print_error)
        if error > 5.01e-6:
            raise ValueError("Reconstructed reward differs from printed native profits")
        mean_profit = exact_profits.mean(axis=0)
        delta = float(((mean_profit-game.profit_nash)/(game.profit_monopoly-game.profit_nash)).mean())
        symmetric = bool(np.all(session["cycle_actions"][:, 0] == session["cycle_actions"][:, 1]))
        classification = ("1-Sym." if symmetric else "1-Asym.") if length == 1 else ("2" if length == 2 else ">=3")
        diagnosis = one_step_diagnostic(game, policy, int(states[0]))
        rows.append(dict(session=session["session"], converged=session["converged"],
                         cycle_class=classification, mean_delta=delta,
                         mean_profit_player0=float(mean_profit[0]), mean_profit_player1=float(mean_profit[1]),
                         episodes_printed=session["episodes"], **diagnosis))
    valid = [row for row in rows if row["converged"]]
    def group_statistics(subset):
        delta = np.array([row["mean_delta"] for row in subset])
        result = dict(sessions=len(subset), mean_delta=float(delta.mean()),
                      std_delta=float(delta.std(ddof=1)) if len(delta)>1 else None,
                      equilibrium_frequency=float(np.mean([row["author_one_step_no_profitable_deviation"] for row in subset])))
        for name in ("on_path", "off_path", "all_states"):
            values = np.array([row[f"paper_one_step_loss_{name}"] for row in subset])
            result[f"q_loss_{name}"] = float(values.mean())
            result[f"std_q_loss_{name}"] = float(values.std(ddof=1)) if len(values)>1 else None
        return result
    recomputed = group_statistics(valid)
    recomputed.update(fixed_price_frequency=float(np.mean([row["cycle_length"]==1 for row in valid])),
                      symmetric_fixed_frequency=float(np.mean([row["cycle_class"]=="1-Sym." for row in valid])),
                      asymmetric_fixed_frequency=float(np.mean([row["cycle_class"]=="1-Asym." for row in valid])),
                      two_cycle_frequency=float(np.mean([row["cycle_length"]==2 for row in valid])),
                      long_cycle_frequency=float(np.mean([row["cycle_length"]>=3 for row in valid])))
    # Native executable summaries are authoritative; the recalculation is audited alongside them.
    prefix = compare_original_prefix(output.parent/"original_smoke", output, game, settings["sessions"])
    repeat_command = ["python", "experiments/run_original.py", "--sessions", str(settings["sessions"]),
                      "--cores", str(execution["cores"]), "--output", str(output.relative_to(ROOT))]
    if execution.get("runtime_path"):
        repeat_command.extend(["--runtime-path", execution["runtime_path"]])
    repeat_command.extend(["--timeout", "600"])
    ci_half = student_t.ppf(.975, len(valid)-1)*recomputed["std_delta"]/np.sqrt(len(valid)) if len(valid)>1 else None
    summary = dict(engine="Unmodified supplied official Windows executable", sessions=len(rows),
                   converged=len(valid), censored=len(rows)-len(valid),
                   mean_delta=native_conv["avgPrGain"], population_std_delta=native_conv["sePrGain"],
                   equilibrium_frequency=native_eq["FlagEQOnPath_Len00"],
                   ci95_mean_delta=([recomputed["mean_delta"]-ci_half,recomputed["mean_delta"]+ci_half]
                                    if ci_half is not None else None),
                   ci_note="Student-t Monte Carlo mean interval from recomputed session values and sample SD; native mean is rounded to 5 decimals",
                   recomputed_from_original_strategies=recomputed,
                   native_vs_recomputed_gain_error=abs(native_conv["avgPrGain"]-recomputed["mean_delta"]),
                   native_vs_recomputed_equilibrium_error=abs(native_eq["FlagEQOnPath_Len00"]-recomputed["equilibrium_frequency"]),
                   maximum_printed_profit_rounding_error=max_print_error,
                   benchmark=dict(price_nash=game.price_nash.tolist(), price_monopoly=game.price_monopoly.tolist(),
                                  profit_nash=game.profit_nash.tolist(), profit_monopoly=game.profit_monopoly.tolist(),
                                  price_grid=game.prices.tolist()),
                   table1_all_states_label="Official Table I R script reads QGapNotOnPath (off-path), not QGapTot",
                   native_truth_sources={"mean_delta":"A_convResults.txt::avgPrGain",
                                         "population_std_delta":"A_convResults.txt::sePrGain (population SD, not SE)",
                                         "equilibrium_frequency":"A_ec.txt::FlagEQOnPath_Len00"},
                   executable_sha256=execution["executable_sha256"], input_sha256=execution["input_sha256"],
                   native_process_command=["baseline.exe"], native_working_directory=str(output.relative_to(ROOT)),
                   reproducible_wrapper_command=repeat_command,
                   wrapper_command_note="Reconstructed from saved execution/input settings; original raw process uses baseline.exe in this directory",
                   two_session_seed_prefix_verification=prefix,
                   approximate_max_training_periods=max(row["episodes_printed"] for row in rows)*settings["iterations_per_episode"],
                   training_periods_precision_note="Approximation only: InfoExperiment stores episode counts to 0.01; period reconstruction can round by about 125 periods",
                   reconstruction="Five-decimal benchmark inputs and sequential grid addition exactly follow author PI_routines; raw logit exp formula")
    if summary["native_vs_recomputed_gain_error"] > 5.1e-6:
        raise RuntimeError("Recomputed profit gain does not match native output rounding")
    if summary["native_vs_recomputed_equilibrium_error"] > 1e-10:
        raise RuntimeError("Recomputed one-step equilibrium frequency does not match native A_ec")
    tables = output / "tables"
    tables.mkdir(exist_ok=True)
    write_csv(tables/"sessions_original.csv", rows)
    table1 = []
    for label in ("1-Sym.", "1-Asym.", "1", "2", ">=3", "All", "Author-one-step"):
        subset = [row for row in valid if label=="All" or
                  (label=="1" and row["cycle_length"]==1) or
                  (label=="Author-one-step" and row["author_one_step_no_profitable_deviation"]) or
                  row["cycle_class"]==label]
        if subset:
            table1.append(dict(group=label, frequency=len(subset)/len(valid), **group_statistics(subset)))
    write_csv(tables/"table1_original.csv", table1)
    comparison = []
    paper = {"mean_delta":.849, "std_delta":.112, "symmetric_fixed_frequency":.277,
             "asymmetric_fixed_frequency":.366, "fixed_price_frequency":.643,
             "two_cycle_frequency":.238, "long_cycle_frequency":.119,
             "equilibrium_frequency":.505, "q_loss_on_path":.002, "q_loss_off_path":.018}
    for metric, reference in paper.items():
        value = (summary["population_std_delta"] if metric=="std_delta" else
                 (summary[metric] if metric in summary else recomputed[metric]))
        comparison.append(dict(metric=metric, paper=reference, reproduced=value,
                               signed_error=value-reference, absolute_error=abs(value-reference),
                               relative_error=abs(value-reference)/abs(reference),
                               source="Table 1, All column, p.3277",
                               note=("Printed All States label uses off-path in original R" if metric=="q_loss_off_path" else
                                     ("Native sePrGain is population SD; recomputed sample SD retained separately" if metric=="std_delta" else ""))))
    write_csv(tables/"paper_comparison.csv", comparison)
    (output/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output/"verification.json").write_text(json.dumps(prefix, indent=2), encoding="utf-8")
    impulse_path = output/"A_irToBR.txt"
    impulse_plot = native_impulse_figure(output, read_native_table(impulse_path)) if impulse_path.exists() else None
    files = [output/"summary.json", output/"verification.json", tables/"sessions_original.csv", tables/"table1_original.csv", tables/"paper_comparison.csv"]
    if impulse_plot:
        files.extend([impulse_plot, tables/"figure4_original.csv"])
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), script_sha256=sha256(__file__),
                    script="experiments/summarize_original.py", execution_manifest_sha256=sha256(execution_path),
                    executable_sha256=sha256(executable),
                    native_inputs_outputs_sha256={name:sha256(output/name) for name in execution["outputs_sha256"]},
                    diagnostic_dependencies_sha256={name:sha256(ROOT/name) for name in
                                                    ("experiments/paper_diagnostics.py", "src/collusion/analysis.py", "experiments/run_original.py")},
                    outputs_sha256={str(path.relative_to(output)):sha256(path) for path in files})
    (output/"summary_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/original_baseline")
    args = parser.parse_args()
    summary = summarize_original(ROOT/args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
