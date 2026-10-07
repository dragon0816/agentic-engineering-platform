from pathlib import Path
import json
workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
print('output exists:', output_dir.exists())
if input_dir.exists():
    for p in sorted(input_dir.iterdir()):
        if p.is_file():
            print('\nFILE:', p.name, 'size=', p.stat().st_size)
            try:
                with p.open('r', encoding='utf-8-sig') as f:
                    for i in range(5):
                        line = f.readline()
                        if not line:
                            break
                        print(f'  L{i+1}:', line.rstrip('\n')[:500])
            except UnicodeDecodeError:
                with p.open('r', encoding='latin-1') as f:
                    for i in range(5):
                        line = f.readline()
                        if not line:
                            break
                        print(f'  L{i+1}:', line.rstrip('\n')[:500])