"""Build a GitHub-ready archive using an explicit inclusion list."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def selected(path):
    relative=path.relative_to(ROOT)
    parts=relative.parts
    if not path.is_file() or any(p in ("__pycache__",".pytest_cache") for p in parts):
        return False
    if path.suffix in (".pyc",".nbc",".nbi",".tmp"):
        return False
    if len(parts)==1:
        return path.name in {"README.md","REPRODUCTION_REPORT.md","LICENSE","THIRD_PARTY_NOTICES.md",
                             "CITATION.cff","pyproject.toml","requirements.txt","requirements-lock.txt",
                             ".gitignore",".gitattributes","reproduce.py"}
    if parts[0] in ("src","experiments","tests","configs","docs","scripts",".github","vendor"):
        return True
    if parts[0]=="notes":
        return path.suffix in (".md",".json")
    if parts[0]=="data":
        return parts[1]=="reference" or relative.as_posix()=="data/source/README.md"
    if parts[0]=="results":
        if path.name=="baseline.exe":
            return False
        if len(parts)==2:
            return path.suffix in (".log",".md") and not path.name.startswith("integration_check") and path.name!="package_build.log"
        return parts[1] in ("validated","four_firms_extended","original_baseline","original_smoke",
                            "final_integration","final_integration_original")
    return False


def main():
    files=sorted(p for p in ROOT.rglob("*") if selected(p))
    records={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
    manifest=ROOT/"DELIVERY_MANIFEST.json"
    manifest.write_text(json.dumps(dict(files=records,excluded="Virtual environment, local papers, input archives, extracted paper text, stale smoke output, duplicate executables"),indent=2),encoding="utf-8")
    archive=ROOT/"project_delivery.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files+[manifest]:
            z.write(path,"calvano-pricing-reproduction/"+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,record in records.items():
            assert hashlib.sha256(z.read("calvano-pricing-reproduction/"+name)).hexdigest()==record["sha256"]
    print(json.dumps(dict(archive=str(archive),files=len(files)+1,bytes=archive.stat().st_size,
                         sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),archive_hashes_verified=True),indent=2))


if __name__=="__main__":
    main()
