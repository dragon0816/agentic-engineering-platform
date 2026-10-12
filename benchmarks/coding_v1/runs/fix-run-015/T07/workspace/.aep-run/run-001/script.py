from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('input files:', [p.name for p in input_dir.iterdir()] if input_dir.exists() else 'NO INPUT DIR')
path = input_dir / 'specs.md'
print('specs.md exists:', path.exists())
if path.exists():
    text = path.read_text(encoding='utf-8')
    print('--- specs.md content start ---')
    print(text)
    print('--- specs.md content end ---')
print('output dir exists:', output_dir.exists())