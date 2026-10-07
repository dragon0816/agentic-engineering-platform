from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
for p in sorted(input_dir.rglob('*')) if input_dir.exists() else []:
    rel = p.relative_to(input_dir)
    print('ITEM:', rel, 'dir' if p.is_dir() else 'file', 'size=' + (str(p.stat().st_size) if p.is_file() else '-'))
    if p.is_file():
        for enc in ('utf-8-sig','utf-8','latin-1'):
            try:
                with p.open('r', encoding=enc) as f:
                    print('  encoding:', enc)
                    for i in range(5):
                        line = f.readline()
                        if not line: break
                        print(f'  L{i+1}:', line.rstrip('\n')[:500])
                break
            except UnicodeDecodeError:
                continue
