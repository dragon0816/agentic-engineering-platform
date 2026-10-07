from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:', sorted(p.name for p in input_dir.iterdir()))
path = input_dir / 'login_sop.md'
print('login_sop.md exists:', path.exists())
if path.exists():
    text = path.read_text(encoding='utf-8')
    print('--- login_sop.md start ---')
    print(text)
    print('--- login_sop.md end ---')
print('output files:', sorted(p.name for p in (workspace/'output').iterdir()) if (workspace/'output').exists() else [])