"""One-command rerun: tests, actual training, paper diagnostics, integrity/replay audit."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    from experiments.restore_assets import restore_assets
    print(restore_assets(), flush=True)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers",type=int,default=2)
    parser.add_argument("--quick",action="store_true",help="Two-session integration check only")
    parser.add_argument("--output",default=None)
    parser.add_argument("--original",action="store_true",help="Also run the author Windows executable")
    parser.add_argument("--runtime-path",default=None,help="Installed Intel runtime directory for --original")
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    config="configs/smoke.json" if args.quick else "configs/validated.json"
    output=args.output or ("results/quick" if args.quick else "results/recheck")
    commands=[
        ["-m","pytest","-q"],
        ["experiments/run.py","--config",config,"--output",output,"--workers",str(args.workers)],
        ["experiments/paper_diagnostics.py","--output",output],
        ["experiments/verify_results.py","--output",output,"--rerun","2" if args.quick else "3"],
    ]
    if not args.quick:
        commands += [
            ["experiments/run.py","--config","configs/four_firms_extended.json","--output",output+"_four_firms_extended","--workers",str(args.workers)],
            ["experiments/verify_results.py","--output",output+"_four_firms_extended","--rerun","0"],
        ]
    if args.original:
        native=["experiments/run_original.py","--sessions","2" if args.quick else "1000",
                "--cores",str(args.workers),"--timeout","600","--output",output+"_original"]
        if args.runtime_path:
            native += ["--runtime-path",args.runtime_path]
        commands += [native,["experiments/summarize_original.py","--output",output+"_original"]]
        if not args.quick:
            commands += [["experiments/compare_table1.py","--output",output+"_original"]]
    for command in commands:
        print("Running:"," ".join(command),flush=True)
        subprocess.run([sys.executable,*command],cwd=root,check=True)
    print(f"All checks passed. Inspect {output}/summary.json and {output}/paper_diagnostics.json",flush=True)


if __name__ == "__main__":
    main()
