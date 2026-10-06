from pathlib import Path
workspace = Path.cwd()
print('Workspace:', workspace)
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('Input files:')
for p in sorted(input_dir.glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
    if p.name.lower() == 'sop.md':
        text = p.read_text(encoding='utf-8')
        print('\n--- sop.md preview ---')
        print(text[:2000])
        print('--- end preview ---')
print('Output dir exists:', output_dir.exists())