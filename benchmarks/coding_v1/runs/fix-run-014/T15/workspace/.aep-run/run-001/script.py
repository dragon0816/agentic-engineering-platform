from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('input files:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
    if p.is_file() and p.name == 'test.log':
        print('sample lines from test.log:')
        with p.open('r', encoding='utf-8', errors='replace') as f:
            for i, line in zip(range(1, 11), f):
                print(f'{i}: {line.rstrip()}')
print('output dir exists:', output_dir.exists())