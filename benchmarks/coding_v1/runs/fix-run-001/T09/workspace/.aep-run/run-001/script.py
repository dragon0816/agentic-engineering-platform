from pathlib import Path
ws=Path.cwd()
print('cwd', ws)
print('input files:')
for p in (ws/'input').rglob('*'):
    print(p.relative_to(ws), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
for name in ['login_sop.md']:
    p=ws/'input'/name
    if p.exists():
        print('\n---', name, '---')
        print(p.read_text(encoding='utf-8'))
print('\nworkspace top:')
for p in ws.iterdir():
    print(p.name, 'dir' if p.is_dir() else 'file')