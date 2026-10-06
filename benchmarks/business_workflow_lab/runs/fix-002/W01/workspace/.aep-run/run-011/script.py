from pathlib import Path
workspace = Path.cwd()
print('Workspace:', workspace)
print('Output exists:', (workspace/'output').exists())
print('Output entries:')
for p in sorted((workspace/'output').glob('*')) if (workspace/'output').exists() else []:
    print('-', p.relative_to(workspace), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
rerun = workspace/'output'/'rerun'
rerun.mkdir(parents=True, exist_ok=True)
print('Created/confirmed:', rerun)
print('Rerun exists:', rerun.exists(), 'is_dir:', rerun.is_dir())