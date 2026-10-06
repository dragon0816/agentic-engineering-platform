from pathlib import Path
import hashlib
import csv
import shutil

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

def rel_posix(path: Path) -> str:
    return path.relative_to(workspace).as_posix()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

if not input_root.exists():
    raise FileNotFoundError(f"Input folder not found: {input_root}")

# Recreate only our output classification tree and manifest; never touch input.
if classified_root.exists():
    shutil.rmtree(classified_root)
classified_root.mkdir(parents=True, exist_ok=True)
output_root.mkdir(parents=True, exist_ok=True)

rows = []
for src in sorted((p for p in input_root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(input_root).as_posix().lower()):
    category = categories.get(src.suffix.lower(), "Other")
    rel_under_files = src.relative_to(input_root)
    dst = classified_root / category / rel_under_files
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    rows.append({
        "original_path": rel_posix(src),
        "new_path": rel_posix(dst),
        "sha256": sha256_file(src),
    })

with manifest_path.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["original_path", "new_path", "sha256"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Copied {len(rows)} files into {classified_root}")
print(f"Wrote manifest: {manifest_path}")
for cat in ["PDF", "Excel", "Image", "Other"]:
    count = sum(1 for r in rows if f"/classified/{cat}/" in r["new_path"])
    print(f"{cat}: {count}")