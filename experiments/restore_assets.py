"""Restore byte-identical archived records in the browser-upload edition."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def restore_assets(root=ROOT, verify_only=False):
    root = Path(root).resolve()
    index = root / "_archives/manifest.json"
    if not index.exists():
        return {"edition": "full", "restored": 0, "already_present": 0}
    manifest = json.loads(index.read_text(encoding="utf-8"))
    # Validate every container before writing anything.
    for item in manifest["archives"]:
        archive = (root / item["path"]).resolve()
        archive.relative_to(root)
        if sha256(archive.read_bytes()) != item["sha256"]:
            raise ValueError(f"Archive hash mismatch: {item['path']}")
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:
                raise ValueError(f"Corrupt archive: {archive.name}")
            for entry in z.infolist():
                name = PurePosixPath(entry.filename)
                if name.is_absolute() or ".." in name.parts or entry.filename not in manifest["files"]:
                    raise ValueError(f"Unexpected archive path: {entry.filename}")
                (root / entry.filename).resolve().relative_to(root)
    restored = existing = 0
    if not verify_only:
        for item in manifest["archives"]:
            with zipfile.ZipFile(root / item["path"]) as z:
                for entry in z.infolist():
                    blob = z.read(entry.filename)
                    expected = manifest["files"][entry.filename]["sha256"]
                    if sha256(blob) != expected:
                        raise ValueError(f"Member hash mismatch: {entry.filename}")
                    target = (root / entry.filename).resolve()
                    target.relative_to(root)
                    if target.exists():
                        if sha256(target.read_bytes()) != expected:
                            raise FileExistsError(f"Existing file differs; preserved without overwrite: {target}")
                        existing += 1
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_name(target.name + ".restore.tmp")
                    temporary.write_bytes(blob)
                    temporary.replace(target)
                    restored += 1
    return dict(edition="browser-upload", archives_verified=len(manifest["archives"]),
                archived_files=len(manifest["files"]), restored=restored,
                already_present=existing, verify_only=verify_only)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(restore_assets(verify_only=args.verify_only), indent=2))
