from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
print('input files:')
for p in sorted((workspace/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
sop = workspace/'input'/'sop.md'
print('\n--- sop.md content preview ---')
if sop.exists():
    text = sop.read_text(encoding='utf-8')
    print(text[:4000])
else:
    print('sop.md not found')