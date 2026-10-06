from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / "input" / "texts"
output_dir = workspace / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "combined.md"

if not input_dir.is_dir():
    raise FileNotFoundError(f"Input directory not found: {input_dir}")

files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix == ".txt"], key=lambda p: p.name)

parts = []
for p in files:
    content = p.read_text(encoding="utf-8")
    parts.append(f"## {p.stem}\n\n{content}")

# Keep each file's content unchanged; only add markdown headings and blank lines between sections.
combined = "\n\n".join(parts)
output_file.write_text(combined, encoding="utf-8")

print(f"Wrote {output_file}")
print(f"Processed {len(files)} file(s):")
for p in files:
    print(p.name)
