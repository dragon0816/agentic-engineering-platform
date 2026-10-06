from pathlib import Path
import shutil
import hashlib
import csv

workspace = Path.cwd()
input_root = workspace / "input" / "files"
output_root = workspace / "output"
classified_root = output_root / "classified"
manifest_path = output_root / "manifest.csv"

categories = {
    ".pdf": "PDF",
    ".xls": "Excel",
    ".xlsx": "Excel",
    ".png": "Image",
    ".jpg": "Image",
    ".jpeg": "Image",
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

if not input_root.exists():
    raise FileNotFoundError(f"Input folder not found: {input_root}")

output_root.mkdir(parents=True, exist_ok=True)
classified_root.mkdir(parents=True, exist_ok=True)

rows = []
files = sorted([p for p in input_root.rglob("*") if p.is_file()], key=lambda p: p.relative_to(input_root).as_posix().lower())

for src in files:
    rel = src.relative_to(input_root)
    category = categories.get(src.suffix.lower(), "Other")
    dst = classified_root / category / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = sha256_file(src)
    rows.append({
        "original_path": (Path("input") / "files" / rel).as_posix(),
        "new_path": (Path("output") / "classified" / category / rel).as_posix(),
        "sha256": digest,
    })

with manifest_path.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["original_path", "new_path", "sha256"])
    writer.writeheader()
    writer.writerows(rows)

counts = {}
for row in rows:
    cat = Path(row["new_path"]).parts[2]
    counts[cat] = counts.get(cat, 0) + 1

print(f"Copied {len(rows)} files from {input_root} to {classified_root}")
print(f"Wrote manifest: {manifest_path}")
for cat in ["PDF", "Excel", "Image", "Other"]:
    print(f"{cat}: {counts.get(cat, 0)}")
