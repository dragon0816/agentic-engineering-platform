from pathlib import Path
sp=Path.cwd()/'.aep-run'/'run-006'/'script.py'
text=sp.read_text(encoding='utf-8', errors='replace')
lines=text.splitlines()
for start,end in [(1,140)]:
    print(f'--- lines {start}-{end} ---')
    for i,line in enumerate(lines[start-1:end], start):
        print(f'{i:04d}: {line}')
