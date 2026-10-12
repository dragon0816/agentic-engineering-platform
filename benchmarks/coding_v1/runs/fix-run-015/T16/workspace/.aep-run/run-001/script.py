from pathlib import Path

ws = Path.cwd()
inp = ws / 'input'
out = ws / 'output'
print('workspace:', ws)
print('input exists:', inp.exists())
print('output exists:', out.exists())
if inp.exists():
    files = sorted([p for p in inp.iterdir() if p.is_file()])
    print('input files:', [p.name for p in files])
    for p in files:
        print('\n---', p.name, '---')
        try:
            with p.open('r', encoding='utf-8') as f:
                for i, line in zip(range(1, 6), f):
                    print(f'{i}: {line.rstrip()}')
        except UnicodeDecodeError:
            with p.open('r', encoding='utf-8-sig', errors='replace') as f:
                for i, line in zip(range(1, 6), f):
                    print(f'{i}: {line.rstrip()}')
