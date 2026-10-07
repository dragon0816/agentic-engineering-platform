from pathlib import Path
workspace = Path.cwd()
print('WORKSPACE', workspace)
for sub in ['input','output']:
    p = workspace / sub
    print(f'[{sub}] exists={p.exists()}')
    if p.exists():
        for f in sorted(p.iterdir()):
            print(' -', f.name, 'file' if f.is_file() else 'dir', f.stat().st_size if f.is_file() else '')

sop = workspace / 'input' / 'login_sop.md'
print('login_sop.md exists=', sop.exists())
if sop.exists():
    text = sop.read_text(encoding='utf-8')
    print('--- login_sop.md start ---')
    print(text[:4000])
    print('--- login_sop.md end ---')