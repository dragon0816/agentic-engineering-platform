from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / "input" / "texts"
output_dir = workspace / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "combined.md"

# Only first-level .txt files, sorted by filename.
files = sorted((p for p in input_dir.iterdir() if p.is_file() and p.suffix == ".txt"), key=lambda p: p.name)

with output_file.open("w", encoding="utf-8", newline="") as out:
    for idx, path in enumerate(files):
        if idx > 0:
            out.write("\n\n")
        out.write(f"## {path.stem}\n\n")
        # Preserve each file's text exactly as read; only add section framing/separators.
        out.write(path.read_text(encoding="utf-8"))

print(f"Wrote {output_file}")
print(f"Merged {len(files)} file(s):")
for path in files:
    print(path.name)
