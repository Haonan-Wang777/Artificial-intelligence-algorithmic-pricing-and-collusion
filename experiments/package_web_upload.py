"""Make a <=100-file browser upload edition without discarding experiment data."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "calvano-pricing-reproduction/"
PART_BYTES = 20 * 1024 * 1024
VISIBLE_RESULTS = {
    "results/README.md", "results/tests.log",
    "results/original_baseline/summary.json",
    "results/original_baseline/table1_validation.json",
    "results/original_baseline/verification.json",
    "results/original_baseline/figures/figure4_original.png",
    "results/original_baseline/tables/table1_original.csv",
    "results/original_baseline/tables/table1_cell_comparison.csv",
    "results/original_baseline/tables/paper_comparison.csv",
    "results/validated/summary.json", "results/validated/paper_diagnostics.json",
    "results/validated/verification.json",
    "results/validated/tables/paper_one_step_comparison.csv",
    "results/validated/tables/table1_author_one_step.csv",
    "results/validated/figures/figure4_impulse_response.png",
    "results/validated/figures/profit_distribution.png",
    "results/validated/figures/learning_dynamics.png",
    "results/validated/figures/figure2_one_step_vs_dynamic.png",
    "results/validated/figures/figures1_2_reduced_grid.png",
    "results/four_firms_extended/summary.json",
    "results/four_firms_extended/verification.json",
}
VENDOR_FILES = {
    "vendor/calvano_original/LICENSE.txt", "vendor/calvano_original/README.md",
    "vendor/calvano_original/VENDOR_MANIFEST.json",
    "vendor/calvano_original/AER_paper_Rscripts/table_I/table_I.R",
    "vendor/calvano_original/AER_paper_Rscripts/table_I/A_InputParameters.txt",
}


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def visible(name):
    if name == "DELIVERY_MANIFEST.json":
        return False
    if name.startswith("results/"):
        return name in VISIBLE_RESULTS
    if name.startswith("vendor/"):
        return name in VENDOR_FILES or name.startswith("vendor/calvano_original/AER_fcode/baseline/")
    return True


def main():
    destination = ROOT / "github_web_upload" / "calvano-pricing-reproduction"
    if destination.exists():
        raise FileExistsError(f"Output already exists; preserve it or choose a fresh folder: {destination}")
    destination.mkdir(parents=True)
    public, archived = {}, {}
    with zipfile.ZipFile(ROOT / "project_delivery.zip") as original:
        for info in original.infolist():
            if info.is_dir():
                continue
            assert info.filename.startswith(PREFIX)
            name = info.filename[len(PREFIX):]
            if name == "DELIVERY_MANIFEST.json":
                continue
            (public if visible(name) else archived)[name] = original.read(info)
    for name in ("experiments/restore_assets.py", "experiments/package_web_upload.py", "GITHUB_UPLOAD_GUIDE.md"):
        public[name] = (ROOT / name).read_bytes()
    preface = (
        "\n> **GitHub网页上传版**：完整数据仍然保留，数千个记录已打包在 `_archives/`。"
        "上传时保留这些小ZIP，**不要展开后再上传**。"
        "[网页上传与本地恢复说明](GITHUB_UPLOAD_GUIDE.md)。"
        "一键复现会自动恢复；手动核验前运行 `python experiments/restore_assets.py`。\n"
    )
    text = public["README.md"].decode("utf-8")
    heading, rest = text.split("\n", 1)
    public["README.md"] = (heading + "\n" + preface + rest).encode("utf-8")
    main_code = public["reproduce.py"].decode("utf-8")
    main_code = main_code.replace("def main():", "def main():\n    from experiments.restore_assets import restore_assets\n    print(restore_assets(), flush=True)", 1)
    public["reproduce.py"] = main_code.encode("utf-8")
    ignore = public[".gitignore"].decode("utf-8")
    for name in archived:
        ignore += "\n/" + name
    public[".gitignore"] = (ignore + "\n").encode("utf-8")
    for name, blob in public.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    groups, group, size = [], [], 0
    for name, blob in sorted(archived.items()):
        if group and size + len(blob) > PART_BYTES:
            groups.append(group)
            group, size = [], 0
        group.append(name)
        size += len(blob)
    if group:
        groups.append(group)
    archive_records = []
    for number, names in enumerate(groups, 1):
        name = f"_archives/records_part_{number:02d}.zip"
        target = destination / name
        target.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for member in names:
                z.writestr(member, archived[member])
        blob = target.read_bytes()
        assert len(blob) < 25 * 1024 * 1024
        archive_records.append(dict(path=name, bytes=len(blob), sha256=digest(blob), files=len(names)))
    index = dict(archives=archive_records, files={name:dict(bytes=len(blob), sha256=digest(blob)) for name, blob in archived.items()},
                 original_delivery_zip_sha256=digest((ROOT / "project_delivery.zip").read_bytes()),
                 note="Original experiment records and author files preserved byte for byte; visible files stay outside containers")
    (destination / "_archives/manifest.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    files = sorted(p for p in destination.rglob("*") if p.is_file())
    assert len(files) + 1 <= 100, f"Too many files: {len(files)+1}"
    assert max(p.stat().st_size for p in files) < 25 * 1024 * 1024
    evidence = dict(upload_file_count=len(files)+1, limit_files=100, file_limit_mib=25,
                    archived_file_count=len(archived), archive_parts=len(groups), data_removed=False,
                    files={p.relative_to(destination).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in files})
    (destination / "UPLOAD_MANIFEST.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    archive = ROOT / "github_web_upload.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(p for p in destination.rglob("*") if p.is_file()):
            z.write(path, PREFIX + path.relative_to(destination).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.infolist()) == evidence["upload_file_count"]
    print(json.dumps(dict(output=str(destination), zip=str(archive), upload_files=evidence["upload_file_count"],
                          archived_files=len(archived), archive_parts=len(groups),
                          largest_file_mib=max(p.stat().st_size for p in files)/1024**2,
                          zip_bytes=archive.stat().st_size), indent=2))


if __name__ == "__main__":
    main()
