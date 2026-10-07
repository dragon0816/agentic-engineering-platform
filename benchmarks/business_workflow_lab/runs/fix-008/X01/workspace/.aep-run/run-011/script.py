from pathlib import Path
root=Path.cwd()
sp=root/'.aep-run'/'run-006'/'script.py'
print('script exists', sp.exists(), 'size', sp.stat().st_size if sp.exists() else None)
text=sp.read_text(encoding='utf-8', errors='replace')
lines=text.splitlines()
for start,end in [(1,80),(80,170),(170,260),(260,360),(360,460)]:
    print(f'\n--- lines {start}-{end} ---')
    for i,line in enumerate(lines[start-1:end], start):
        print(f'{i:04d}: {line}')
