from pathlib import Path
import json
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
for path in sorted(input_dir.iterdir()):
    if path.is_file():
        print('\nFILE:', path.name, 'size=', path.stat().st_size)
        try:
            with path.open('r', encoding='utf-8') as f:
                for i in range(1, 6):
                    line = f.readline()
                    if not line:
                        break
                    print(f'  line {i}:', line.rstrip('\n'))
        except UnicodeDecodeError:
            with path.open('r', encoding='utf-8-sig') as f:
                for i in range(1, 6):
                    line = f.readline()
                    if not line:
                        break
                    print(f'  line {i}:', line.rstrip('\n'))
