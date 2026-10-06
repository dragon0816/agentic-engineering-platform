from pathlib import Path
import shutil
import hashlib
import csv

workspace = Path.cwd()
input_root = workspace / "input" / "files"
output_root = workspace / "output"
classified_root = output_root / "classified"
manifest_path = output_root / "manifest.csv"

if not input_root.exists() or not input_root.is_dir():
    raise SystemExit(f"Input folder not found: {input_root}")

categories = {
    "pdf": "PDF",
    "xls": "Excel",
    "xlsx": "Excel",
    "png": "Image",
    "jpg": "Image",
    "jpeg": "Image",
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

rows = []
counts = {"PDF": 0, "Excel": 0, "Image": 0, "Other": 0}

# Ensure output folders exist.
for category in counts:
    (classified_root / category).mkdir(parents=True, exist_ok=True)

for src in sorted((p for p in input_root.rglob("*") if p.is_file()), key=lambda p: str(p.relative_to(input_root)).lower()):
    rel = src.relative_to(input_root)
    ext = src.suffix[1:].lower()
    category = categories.get(ext, "Other")
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(src)
    shutil.copy2(src, dst)
    counts[category] += 1
    rows.append({
        "original_path": str(src.relative_to(workspace)).replace("\\", "/"),
        "new_path": str(dst.relative_to(workspace)).replace("\\", "/"),
        "sha256": digest,
    })

output_root.mkdir(parents=True, exist_ok=True)
with manifest_path.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["original_path", "new_path", "sha256"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Copied {len(rows)} files from {input_root} to {classified_root}")
for category in ["PDF", "Excel", "Image", "Other"]:
    print(f"{category}: {counts[category]}")
print(f"Manifest: {manifest_path}")
