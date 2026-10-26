"""Compare every printed numeric cell of paper Table 1 with the official run.

Reference values are manually transcribed from Table 1, AER 110(10), p.3277.
They are reference targets, never synthetic experiment results. Reproduced raw
values come exclusively from tables/table1_original.csv, itself reconstructed
from the actually executed official binary's 1000 saved strategies.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("1-Sym.", "1-Asym.", "1", "2", ">=3", "All", "Author-one-step")
# Seven entries per printed row, in the exact column order of Table 1.
REFERENCE = {
    "frequency": (.277, .366, .643, .238, .119, 1.000, .505),
    "mean_delta": (.866, .855, .860, .846, .793, .849, .854),
    "std_delta": (.115, .114, .114, .104, .097, .112, .108),
    "equilibrium_frequency": (.686, .661, .672, .294, .025, .505, 1.000),
    "q_loss_on_path": (.001, .001, .001, .002, .004, .002, .000),
    "std_q_loss_on_path": (.002, .004, .003, .003, .006, .004, .000),
    # The paper prints 'all states', while its own R script reads off-path.
    "q_loss_off_path": (.018, .018, .018, .018, .018, .018, .018),
    "std_q_loss_off_path": (.006, .007, .006, .006, .006, .006, .006),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference_paper_hash():
    paper=ROOT/"data/source/paper.pdf"
    if paper.exists():
        return digest(paper)
    provenance=json.loads((ROOT/"notes/source_manifest.json").read_text(encoding="utf-8"))
    return next(item["sha256"] for item in provenance["provided_files"]
                if item["archive_member"].endswith("/T3-Artificial intelligence algorithmic pricing, and collusion.pdf"))


def compare_table1(output):
    output = Path(output)
    source = output/"tables"/"table1_original.csv"
    with source.open(encoding="utf-8", newline="") as stream:
        reproduced = {row["group"]:row for row in csv.DictReader(stream)}
    rows = []
    for metric, values in REFERENCE.items():
        for group, reference in zip(GROUPS, values):
            value = float(reproduced[group][metric])
            paper_printed, reproduced_printed = f"{reference:.3f}", f"{value:.3f}"
            rows.append(dict(metric=metric, group=group,
                             printed_paper_value=paper_printed, raw_reproduced_value=value,
                             reproduced_rounded_3dp=reproduced_printed,
                             signed_error=value-reference, absolute_error=abs(value-reference),
                             round_match=paper_printed==reproduced_printed,
                             source="Calvano et al. (2020), Table 1, AER p.3277"))
    destination = output/"tables"/"table1_cell_comparison.csv"
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    validation = dict(total_cells=len(rows), matched_at_three_decimals=sum(row["round_match"] for row in rows),
                      all_match_at_three_decimals=all(row["round_match"] for row in rows),
                      reference_source="Calvano et al. (2020), Artificial Intelligence, Algorithmic Pricing, and Collusion, Table 1, AER 110(10), p.3277",
                      reference_method="Manual transcription of 8 printed rows x 7 printed columns, including Nash column",
                      caveat="Agreement at reported precision, not equality of unrounded values; original Table I R script labels off-path Q-loss as all states",
                      source_table_sha256=digest(source),
                      source_paper_pdf_sha256=reference_paper_hash(),
                      script_sha256=digest(__file__),
                      comparison_csv_sha256=digest(destination))
    (output/"table1_validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    return validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/original_baseline")
    args = parser.parse_args()
    print(json.dumps(compare_table1(ROOT/args.output), indent=2))


if __name__ == "__main__":
    main()
