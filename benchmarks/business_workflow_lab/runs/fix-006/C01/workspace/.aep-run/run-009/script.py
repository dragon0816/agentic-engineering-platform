from pathlib import Path
ws=Path.cwd()
p=ws/'.aep-run'/'run-007'/'output.txt'
print('output exists:', p.exists(), 'size:', p.stat().st_size if p.exists() else None)
if p.exists():
    text=p.read_text(encoding='utf-8', errors='replace')
    print('--- output tail ---')
    for line in text.splitlines()[-80:]:
        print(line)
    print('--- traceback lines ---')
    for i,line in enumerate(text.splitlines(), start=1):
        if 'Traceback' in line or 'AssertionError' in line or 'Error' in line or 'Exception' in line:
            print(i, line)
