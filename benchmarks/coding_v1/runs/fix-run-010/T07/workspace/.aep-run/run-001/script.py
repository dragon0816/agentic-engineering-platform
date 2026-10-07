from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
input_dir = ws / 'input'
print('input files:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)

spec = input_dir / 'specs.md'
print('\n--- specs.md preview ---')
text = spec.read_text(encoding='utf-8')
print(text[:4000])
print('--- end preview ---')

# rough paragraph split preview
parts = [x.strip() for x in text.split('\n\n') if x.strip()]
print('\nparagraph/block count:', len(parts))
for i, part in enumerate(parts[:10], 1):
    print(f'\n[block {i}]')
    print(part[:500])