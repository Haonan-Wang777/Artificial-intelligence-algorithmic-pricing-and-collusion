"""Derive all tables and figures from saved session records (no synthetic results)."""
from pathlib import Path
import csv
import json
import numpy as np
from scipy.stats import t as student_t
from .model import Game

PAPER = {"mean_delta": .849, "std_delta": .112, "fixed_price_frequency": .643,
         "symmetric_fixed_frequency": .277, "two_cycle_frequency": .238,
         "long_cycle_frequency": .119, "equilibrium_frequency": .505,
         "q_loss_on_path": .002, "q_loss_all_states": .018}


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(records):
    valid = [r for r in records if r["converged"]]
    summary = dict(sessions=len(records), converged=len(valid), censored=len(records)-len(valid))
    if not valid:
        return summary
    delta = np.array([r["mean_delta"] for r in valid])
    n = len(delta)
    std = float(delta.std(ddof=1)) if n > 1 else 0.
    half = float(student_t.ppf(.975,n-1)*std/np.sqrt(n)) if n > 1 else None
    summary.update(mean_delta=float(delta.mean()), std_delta=std,
                   ci95_delta=[float(delta.mean()-half),float(delta.mean()+half)] if half is not None else None,
                   mean_steps=float(np.mean([r["steps"] for r in valid])),
                   max_steps=max(r["steps"] for r in records),
                   mean_price=np.mean([r["mean_price"] for r in valid],axis=0).tolist(),
                   mean_profit=np.mean([r["mean_profit"] for r in valid],axis=0).tolist(),
                   fixed_price_frequency=float(np.mean([r["cycle_length"] == 1 for r in valid])),
                   symmetric_fixed_frequency=float(np.mean([r["cycle_class"] == "1-Sym." for r in valid])),
                   two_cycle_frequency=float(np.mean([r["cycle_length"] == 2 for r in valid])),
                   long_cycle_frequency=float(np.mean([r["cycle_length"] >= 3 for r in valid])))
    diagnosed = [r for r in valid if r.get("is_equilibrium") is not None]
    if diagnosed:
        summary.update(equilibrium_frequency=float(np.mean([r["is_equilibrium"] for r in diagnosed])),
                       q_loss_on_path=float(np.mean([r["q_loss_on_path"] for r in diagnosed])),
                       q_loss_all_states=float(np.mean([r["q_loss_all_states"] for r in diagnosed])),
                       max_bellman_residual=max(r["bellman_residual"] for r in diagnosed))
    impulses = [r["impulse"] for r in valid if "impulse" in r]
    if impulses:
        summary["incentive_compatible_frequency"] = float(np.mean([x["incentive_compatible"] for x in impulses]))
    return summary


def build_results(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size":10, "figure.dpi":130, "savefig.dpi":180,
                         "axes.spines.top":False, "axes.spines.right":False})
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_text())
    specs = manifest["config"]["scenarios"]
    tables = output / "tables"; tables.mkdir(exist_ok=True)
    figures = output / "figures"; figures.mkdir(exist_ok=True)
    groups, summaries, all_rows = {}, {}, []
    for spec in specs:
        folder = output / spec["name"]
        if not folder.exists():
            continue
        records = [json.loads(p.read_text()) for p in sorted(folder.glob("session_*.json"))]
        if not records:
            continue
        groups[spec["name"]] = records
        summary = summarize(records)
        summary.update(alpha=spec["alpha"], beta=spec["beta"], game=spec.get("game", {}))
        summaries[spec["name"]] = summary
        for r in records:
            row = {k:r.get(k) for k in ("index","seed","steps","converged","final_state","mean_delta","cycle_length","cycle_class","is_equilibrium","q_loss_on_path","q_loss_all_states","bellman_residual","elapsed_seconds")}
            all_rows.append(dict(scenario=spec["name"], **row))
    (output / "summary.json").write_text(json.dumps(summaries,indent=2), encoding="utf-8")
    write_csv(tables / "sessions.csv", all_rows)
    write_csv(tables / "scenarios.csv", [dict(scenario=name, **{k:v for k,v in s.items() if not isinstance(v,(dict,list))}) for name,s in summaries.items()])
    # Comparison uses only numbers printed in Table 1 / Section V.A, not digitized figure pixels.
    if "baseline" in summaries and "mean_delta" in summaries["baseline"]:
        baseline = summaries["baseline"]
        comparison = []
        for metric, reference in PAPER.items():
            if metric not in baseline:
                continue
            actual = baseline[metric]
            comparison.append(dict(metric=metric,paper=reference,reproduced=actual,
                                   signed_error=actual-reference,absolute_error=abs(actual-reference),
                                   relative_error=abs(actual-reference)/abs(reference),
                                   source="Table 1, All column, p.3277"))
        for name, reference in (("three_firms",.64),("four_firms",.56)):
            if name in summaries and "mean_delta" in summaries[name]:
                actual = summaries[name]["mean_delta"]
                comparison.append(dict(metric=f"{name}_delta",paper=reference,reproduced=actual,
                                       signed_error=actual-reference,absolute_error=abs(actual-reference),
                                       relative_error=abs(actual-reference)/reference,source="Section V.A, p.3288 (rounded)"))
        write_csv(tables / "paper_comparison.csv",comparison)
        records = [r for r in groups["baseline"] if r["converged"]]
        cycle_rows = []
        for label in ("1-Sym.","1-Asym.","1","2",">=3","All","Nash"):
            subset = [r for r in records if label == "All" or
                      (label == "1" and r["cycle_length"] == 1) or
                      (label == "Nash" and r.get("is_equilibrium")) or r["cycle_class"] == label]
            if subset:
                cycle_rows.append(dict(group=label, frequency=len(subset)/len(records),
                                       **{k:v for k,v in summarize(subset).items() if k in
                                          ("sessions","mean_delta","std_delta","equilibrium_frequency","q_loss_on_path","q_loss_all_states")}))
        write_csv(tables / "table1_reproduced.csv",cycle_rows)
        fig, ax = plt.subplots(figsize=(7.2,4.2))
        ax.hist([r["mean_delta"] for r in records], bins=25,color="#1c788b",alpha=.85)
        ax.axvline(.849,color="#bf5438",linestyle="--",label="Paper mean: 0.849")
        ax.axvline(baseline["mean_delta"],color="#233246",label=f"Reproduced mean: {baseline['mean_delta']:.3f}")
        ax.set(xlabel="Normalized profit gain (Delta)",ylabel="Sessions",title=f"Representative experiment: n={len(records)} converged sessions")
        ax.legend(); fig.tight_layout(); fig.savefig(figures / "profit_distribution.png"); plt.close(fig)
        impulses = [r["impulse"] for r in records if "impulse" in r]
        if impulses:
            paths = np.array([x["prices"] for x in impulses])
            baseline_paths = np.array([x["baseline_prices"] for x in impulses])
            means = paths.mean(axis=0); errors = paths.std(axis=0,ddof=1)/np.sqrt(len(paths)) if len(paths)>1 else np.zeros_like(means)
            times = impulses[0]["time"]
            ir_rows = [dict(time=t,deviator_price=means[i,0],opponent_price=means[i,1],
                            deviator_se=errors[i,0],opponent_se=errors[i,1],
                            baseline_price=float(baseline_paths[:,i,:].mean()),sessions=len(paths)) for i,t in enumerate(times)]
            write_csv(tables / "figure4_impulse.csv",ir_rows)
            fig,ax = plt.subplots(figsize=(7.2,4.2))
            for player,label,color,marker in ((0,"Deviating agent","#bf5438","s"),(1,"Other agent","#1c788b","o")):
                ax.plot(times,means[:,player],label=label,color=color,marker=marker,markersize=4)
                ax.fill_between(times,means[:,player]-1.96*errors[:,player],means[:,player]+1.96*errors[:,player],color=color,alpha=.12)
            g=Game()
            ax.axhline(g.price_nash[0],color="gray",linestyle=":",label="Nash benchmark")
            ax.axhline(g.price_monopoly[0],color="gray",linestyle="--",label="Monopoly benchmark")
            ax.axhline(float(baseline_paths.mean()),color="#233246",linestyle="-.",label="Undisturbed cycle mean")
            ax.set(xlabel="Time (forced static best response at t=1)",ylabel="Price",title=f"Figure 4 reproduction; phase average within session, n={len(paths)}")
            ax.legend(fontsize=8,ncol=2); fig.tight_layout(); fig.savefig(figures / "figure4_impulse_response.png"); plt.close(fig)
        # Complete common prefix avoids survivorship bias from stopping converged sessions.
        histories = [np.load(output / "baseline" / r["snapshot"])["history"] for r in records]
        length = min(min(len(h) for h in histories),50)
        if length:
            g=Game(); gains=np.array([(h[:length,1:].mean(axis=1)-g.profit_nash.mean())/(g.profit_monopoly.mean()-g.profit_nash.mean()) for h in histories])
            mean=gains.mean(axis=0); se=gains.std(axis=0,ddof=1)/np.sqrt(len(gains)) if len(gains)>1 else mean*0
            time=histories[0][:length,0]
            write_csv(tables / "learning_curve.csv",[dict(period=int(t),mean_delta=float(d),se=float(e),sessions=len(gains)) for t,d,e in zip(time,mean,se)])
            fig,ax=plt.subplots(figsize=(7.2,4.2)); ax.plot(time,mean,color="#1c788b"); ax.fill_between(time,mean-1.96*se,mean+1.96*se,color="#1c788b",alpha=.15)
            ax.set(xlabel="Training periods",ylabel="Realized block profit gain",title="Learning dynamics (all baseline sessions, complete common prefix)")
            fig.tight_layout();fig.savefig(figures / "learning_dynamics.png");plt.close(fig)
    grid=[(name,s) for name,s in summaries.items() if (name.startswith("grid_") or name=="baseline") and "mean_delta" in s]
    if len(grid)>1:
        alphas=sorted(set(s["alpha"] for _,s in grid)); betas=sorted(set(s["beta"] for _,s in grid))
        fig,axes=plt.subplots(1,2,figsize=(10,4))
        for ax,metric,title in zip(axes,("mean_delta","equilibrium_frequency"),("Profit gain (Figure 1 subset)","Nash frequency (Figure 2 subset)")):
            values=np.full((len(alphas),len(betas)),np.nan)
            for name,s in grid:
                if metric in s: values[alphas.index(s["alpha"]),betas.index(s["beta"])]=s[metric]
            im=ax.imshow(values,origin="lower",aspect="auto",cmap="viridis",vmin=0,vmax=1)
            ax.set_xticks(range(len(betas)),[f"{b*1e5:g}" for b in betas]); ax.set_yticks(range(len(alphas)),[f"{a:g}" for a in alphas]); ax.set(xlabel="beta x 1e5",ylabel="alpha",title=title)
            for name,s in grid:
                if metric in s:ax.text(betas.index(s["beta"]),alphas.index(s["alpha"]),f"{s[metric]:.3f}\nn={s['converged']}",ha="center",va="center",color="white",fontsize=9)
            fig.colorbar(im,ax=ax,fraction=.045)
        fig.suptitle("Reduced parameter grid; no interpolation to the original 100 x 100 grid",fontsize=11)
        fig.tight_layout();fig.savefig(figures / "figures1_2_reduced_grid.png");plt.close(fig)


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("output",nargs="?",default="results/validated")
    build_results(parser.parse_args().output)
