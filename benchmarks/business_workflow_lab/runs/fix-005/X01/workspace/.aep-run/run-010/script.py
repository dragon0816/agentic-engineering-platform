from pathlib import Path
import os, json, csv
ws=Path.cwd()
print('WORKSPACE', ws)
print('TOP FILES')
for p in sorted(ws.iterdir()):
    print(p.name, 'dir' if p.is_dir() else p.stat().st_size)
print('\nOUTPUT FILES')
out=ws/'output'
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(p.relative_to(ws), p.stat().st_size)
print('\nINPUT FILES')
inp=ws/'input'
for p in sorted(inp.rglob('*')):
    if p.is_file():
        print(p.relative_to(ws), p.stat().st_size)
        if p.suffix.lower()=='.csv':
            with p.open(newline='', encoding='utf-8-sig') as f:
                rows=list(csv.reader(f))
            print('  headers/sample:', rows[:3])
print('\nAEP RUNS')
runroot=ws/'.aep-run'
if runroot.exists():
    for p in sorted(runroot.rglob('*')):
        if p.is_file() and (p.name.endswith('.py') or p.name.endswith('.txt') or p.name.endswith('.log')):
            print(p.relative_to(ws), p.stat().st_size)
            if p.name.endswith('.py'):
                txt=p.read_text(encoding='utf-8', errors='replace')
                print('  first 800 chars:', repr(txt[:800]))
