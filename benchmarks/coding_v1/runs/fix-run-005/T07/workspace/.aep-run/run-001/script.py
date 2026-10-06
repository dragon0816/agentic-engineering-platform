from pathlib import Path
workspace=Path.cwd()
print('CWD:', workspace)
print('Input files:')
for p in sorted((workspace/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
md=workspace/'input'/'specs.md'
print('\n--- specs.md preview ---')
if md.exists():
    text=md.read_text(encoding='utf-8')
    print(text[:2000])
    print('--- end preview, length', len(text), '---')
else:
    print('specs.md not found')