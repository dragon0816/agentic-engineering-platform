from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
out_path = output_dir / 'combined.md'

if not input_dir.exists() or not input_dir.is_dir():
    raise SystemExit(f'Missing input directory: {input_dir}')

files = sorted(
    [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'],
    key=lambda p: p.name,
)

parts = []
for p in files:
    content = p.read_text(encoding='utf-8')
    parts.append(f'## {p.stem}\n\n{content}')

combined = '\n\n'.join(parts)
out_path.write_text(combined, encoding='utf-8')

print('Wrote:', out_path)
print('Merged files:', [p.name for p in files])
print('Output bytes:', out_path.stat().st_size)

# Verification: reopen output and confirm exact expected composition, source files untouched by this script.
reopened = out_path.read_text(encoding='utf-8')
expected = '\n\n'.join(f'## {p.stem}\n\n{p.read_text(encoding="utf-8")}' for p in files)
checks = {
    'output_exists': out_path.exists(),
    'output_name_is_combined_md': out_path.name == 'combined.md',
    'output_under_output_folder': out_path.parent.resolve() == output_dir.resolve(),
    'only_first_level_txt_count': len(files),
    'content_matches_expected_headers_and_original_contents': reopened == expected,
    'ignored_non_txt_and_subfolders': all(p.is_file() and p.suffix == '.txt' and p.parent == input_dir for p in files),
}
print('Verification:')
for k, v in checks.items():
    print(f'- {k}: {v}')
if not all(v if isinstance(v, bool) else True for v in checks.values()):
    raise SystemExit('Verification failed')
