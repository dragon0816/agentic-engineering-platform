from pathlib import Path
root=Path.cwd()
print('AEP RUN DIRS:')
for d in sorted((root/'.aep-run').glob('run-*')):
    print('-', d.relative_to(root))
    for f in d.glob('*'):
        print('   ', f.name, 'size', f.stat().st_size)
# Print tail of likely latest scripts to identify validation failure text embedded in script.
latest = sorted((root/'.aep-run').glob('run-*'))[-5:]
for d in latest:
    sp=d/'script.py'
    print('\nSCRIPT', sp.relative_to(root), 'exists', sp.exists())
    if sp.exists():
        txt=sp.read_text(encoding='utf-8', errors='replace')
        print('len', len(txt))
        print(txt[-4000:])
