from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
print('input files:')
for p in sorted((workspace/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
sop = workspace/'input'/'sop.md'
print('\nsop.md exists:', sop.exists())
if sop.exists():
    text = sop.read_text(encoding='utf-8')
    print('--- sop.md first 1200 chars ---')
    print(text[:1200])
    print('--- total chars:', len(text), '---')