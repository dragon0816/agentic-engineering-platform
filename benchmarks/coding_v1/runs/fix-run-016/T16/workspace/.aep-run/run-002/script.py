from pathlib import Path
base=Path('input')
print('input exists:', base.exists())
print('absolute:', base.resolve())
paths=list(base.rglob('*')) if base.exists() else []
print('path_count:', len(paths))
for p in sorted(paths):
    print(('DIR ' if p.is_dir() else 'FILE'), str(p), 'size' if p.is_file() else '', p.stat().st_size if p.is_file() else '')
    if p.is_file():
        try:
            text=p.read_text(encoding='utf-8')
        except Exception as e:
            try:
                text=p.read_text(encoding='utf-8-sig', errors='replace')
            except Exception as e2:
                print('  cannot read text:', repr(e), repr(e2)); continue
        lines=text.splitlines()
        print('  lines:', len(lines))
        for i,line in enumerate(lines[:5],1): print(f'  {i}: {line[:300]}')
