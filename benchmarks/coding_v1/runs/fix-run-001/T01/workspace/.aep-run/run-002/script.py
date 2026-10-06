from pathlib import Path
import os

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / 'combined.md'

if not input_dir.exists():
    raise FileNotFoundError(str(input_dir))

files = [p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt']
files.sort(key=lambda p: p.name)

parts = []
for p in files:
    data = p.read_text(encoding='utf-8')
    parts.append('## ' + p.stem + '\n\n' + data)

output_file.write_text('\n\n'.join(parts), encoding='utf-8')

print('created=' + str(output_file))
print('count=' + str(len(files)))
print('names=' + ','.join(p.name for p in files))
print('size=' + str(output_file.stat().st_size))