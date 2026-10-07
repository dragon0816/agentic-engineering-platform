from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
input_dir = ws / 'input'
output_dir = ws / 'output'
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
    if p.name.lower() == 'sop.md':
        text = p.read_text(encoding='utf-8')
        print('\n--- sop.md first 1200 chars ---')
        print(text[:1200])
        print('--- end sample ---')
print('output exists:', output_dir.exists())