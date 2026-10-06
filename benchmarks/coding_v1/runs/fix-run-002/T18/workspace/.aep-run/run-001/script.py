from pathlib import Path
ws=Path.cwd()
print('cwd', ws)
for p in [ws/'input'/'export.py', ws/'input'/'input.csv', ws/'input'/'DEPENDENCIES.txt']:
    print('\n---', p.relative_to(ws), 'exists=', p.exists(), '---')
    if p.exists():
        data=p.read_text(encoding='utf-8', errors='replace')
        print(data[:4000])
