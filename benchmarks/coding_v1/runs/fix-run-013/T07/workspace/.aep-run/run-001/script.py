from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
    if p.name.lower() == 'specs.md':
        text = p.read_text(encoding='utf-8')
        print('\n--- specs.md preview ---')
        print(text[:2000])
        print('--- end preview ---')
