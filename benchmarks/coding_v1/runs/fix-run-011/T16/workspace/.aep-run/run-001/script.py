from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
for p in sorted(input_dir.iterdir()):
    if p.is_file():
        print('\nFILE:', p.name, 'size=', p.stat().st_size)
        try:
            with p.open('r', encoding='utf-8-sig') as f:
                for i, line in zip(range(5), f):
                    print(f'  line {i+1}:', repr(line.rstrip('\n')))
        except UnicodeDecodeError:
            with p.open('r', encoding='utf-8', errors='replace') as f:
                for i, line in zip(range(5), f):
                    print(f'  line {i+1}:', repr(line.rstrip('\n')))