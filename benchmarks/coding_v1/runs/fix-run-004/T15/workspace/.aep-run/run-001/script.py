from pathlib import Path
workspace = Path.cwd()
print('cwd:', workspace)
input_dir = workspace / 'input'
print('input exists:', input_dir.exists())
for p in sorted(input_dir.iterdir()):
    print('file:', p.name, 'size:', p.stat().st_size)
    if p.is_file():
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = p.read_text(encoding='utf-8-sig')
        print('first lines:')
        for i, line in enumerate(text.splitlines()[:10], 1):
            print(f'{i}: {line!r}')