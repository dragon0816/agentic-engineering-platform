from pathlib import Path
ws=Path.cwd()
for rn in ['run-003','run-004']:
    p=ws/'.aep-run'/rn/'script.py'
    print('\n---', rn, 'exists', p.exists(), '---')
    if p.exists():
        lines=p.read_text(encoding='utf-8', errors='replace').splitlines()
        print('line_count', len(lines))
        for i,line in enumerate(lines, start=1):
            if 'assert' in line or 'date_norm' in line or 'Summary' in line or 'B3' in line or 'D3' in line or 'raise ' in line:
                print(f'{i}: {line}')
        print('\nLast 70 lines:')
        for i,line in enumerate(lines[-70:], start=max(1,len(lines)-69)):
            print(f'{i}: {line}')
