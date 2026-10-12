from pathlib import Path
import hashlib

workspace = Path.cwd()
input_root = workspace / 'input'
input_dir = input_root / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
out_path = output_dir / 'combined.md'

# Record input file hashes before work to confirm inputs are not modified.
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

input_files_all = [p for p in input_root.rglob('*') if p.is_file()] if input_root.exists() else []
before_hashes = {str(p.relative_to(workspace)): sha256(p) for p in input_files_all}

# Only first-level .txt files under input/texts, sorted by filename.
txt_files = sorted(
    [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for idx, path in enumerate(txt_files):
    content = path.read_text(encoding='utf-8')
    section = f"## {path.stem}\n\n" + content
    parts.append(section)

combined = "\n\n".join(parts)
out_path.write_text(combined, encoding='utf-8', newline='')

# Reopen output and verify stated requirements.
actual = out_path.read_text(encoding='utf-8')
expected = "\n\n".join(
    [f"## {p.stem}\n\n" + p.read_text(encoding='utf-8') for p in txt_files]
)

after_hashes = {str(p.relative_to(workspace)): sha256(p) for p in input_files_all}
checks = []
checks.append(('output file exists', out_path.exists()))
checks.append(('output file name is combined.md', out_path.name == 'combined.md'))
checks.append(('output is in output folder', out_path.parent == output_dir))
checks.append(('content equals expected sorted first-level .txt merge', actual == expected))
checks.append(('included files exactly first-level .txt', [p.name for p in txt_files] == ['a.txt', 'b.txt', 'empty.txt']))
checks.append(('ignored non-txt and subfolders by construction', all(p.parent == input_dir and p.suffix == '.txt' and p.is_file() for p in txt_files)))
checks.append(('input files unchanged', before_hashes == after_hashes))

print('merged files:', [p.name for p in txt_files])
print('output:', out_path)
print('output size bytes:', out_path.stat().st_size)
print('output preview repr:', repr(actual[:300]))
for name, ok in checks:
    print(f'CHECK {name}:', 'PASS' if ok else 'FAIL')

if not all(ok for _, ok in checks):
    raise SystemExit('One or more checks failed')
