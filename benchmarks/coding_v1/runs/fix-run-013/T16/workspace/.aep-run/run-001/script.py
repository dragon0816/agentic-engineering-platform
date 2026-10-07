from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input_dir exists:', input_dir.exists())
for p in sorted(input_dir.iterdir() if input_dir.exists() else []):
    print('\nFILE:', p.name, 'size=', p.stat().st_size)
    if p.is_file():
        try:
            with p.open('r', encoding='utf-8-sig') as f:
                for i, line in zip(range(1, 6), f):
                    print(f'{i}: {line.rstrip()}')
        except UnicodeDecodeError:
            with p.open('r', encoding='cp950', errors='replace') as f:
                for i, line in zip(range(1, 6), f):
                    print(f'{i}: {line.rstrip()}')