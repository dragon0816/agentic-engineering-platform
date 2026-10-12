from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
print('input files:')
for p in sorted((workspace/'input').glob('*')):
    print(' -', p.name, p.stat().st_size, 'bytes')
md = workspace/'input'/'specs.md'
print('\nspecs.md exists:', md.exists())
if md.exists():
    text = md.read_text(encoding='utf-8')
    print('--- specs.md content start ---')
    print(text)
    print('--- specs.md content end ---')