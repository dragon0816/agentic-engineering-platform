from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
input_dir = workspace / 'input'
print('input files:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
log = input_dir / 'test.log'
print('test.log exists:', log.exists())
if log.exists():
    print('first lines:')
    with log.open('r', encoding='utf-8', errors='replace') as f:
        for i, line in zip(range(1, 11), f):
            print(f'{i}: {line.rstrip()}')