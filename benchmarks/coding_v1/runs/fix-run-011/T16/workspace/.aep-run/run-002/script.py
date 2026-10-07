from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
print('output exists:', output_dir.exists())
print('\nRecursive input listing:')
if input_dir.exists():
    entries = list(input_dir.rglob('*'))
    print('entry_count:', len(entries))
    for p in entries:
        print(('DIR ' if p.is_dir() else 'FILE'), p.relative_to(workspace), 'size=' + (str(p.stat().st_size) if p.is_file() else '-'))
        if p.is_file():
            try:
                with p.open('r', encoding='utf-8-sig') as f:
                    for i, line in zip(range(5), f):
                        print(f'  line {i+1}:', repr(line.rstrip('\n')))
            except Exception as e:
                print('  could not preview:', type(e).__name__, str(e))
print('\nWorkspace listing:')
for p in sorted(workspace.iterdir()):
    print(('DIR ' if p.is_dir() else 'FILE'), p.name)