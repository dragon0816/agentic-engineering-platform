from pathlib import Path
ws = Path.cwd()
inp = ws / 'input'
out = ws / 'output'
print('workspace:', ws)
print('input exists:', inp.exists())
print('output exists:', out.exists())
paths = sorted([p for p in inp.rglob('*')]) if inp.exists() else []
print('input entries:', len(paths))
for p in paths:
    rel = p.relative_to(inp)
    print('\nENTRY:', rel, 'dir' if p.is_dir() else 'file', 'size:', p.stat().st_size)
    if p.is_file():
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = p.read_text(encoding='utf-8-sig')
        lines = text.splitlines()
        print('line_count:', len(lines))
        for i, line in enumerate(lines[:5], 1):
            print(f'  sample {i}:', line[:300])