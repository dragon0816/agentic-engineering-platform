from pathlib import Path
import os, csv, json
workspace = Path.cwd()
print('workspace', workspace)
for p in sorted((workspace/'input').rglob('*')):
    print('INPUT', p.relative_to(workspace), 'dir' if p.is_dir() else f'file {p.stat().st_size} bytes')
print('output exists', (workspace/'output').exists())
for p in sorted((workspace/'output').glob('*')):
    st=p.stat()
    print('OUTPUT', p.relative_to(workspace), st.st_size, 'bytes', 'readonly' if not os.access(p, os.W_OK) else 'writable')
sop = workspace/'input'/'supplied_sop.md'
print('--- SOP sample ---')
print(sop.read_text(encoding='utf-8')[:1000])
csv_path = workspace/'input'/'data'/'test_results.csv'
print('--- CSV headers/sample ---')
with csv_path.open(newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f)
    for i,row in zip(range(10), r):
        print(row)
