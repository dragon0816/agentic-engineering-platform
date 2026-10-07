from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
print('input files:')
for p in sorted((workspace/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)

sop = workspace/'input'/'sop.md'
print('\nsop.md exists:', sop.exists())
if sop.exists():
    text = sop.read_text(encoding='utf-8')
    print('--- first 1200 chars ---')
    print(text[:1200])
    print('--- lines preview ---')
    for i, line in enumerate(text.splitlines()[:80], 1):
        print(f'{i:03}: {line}')