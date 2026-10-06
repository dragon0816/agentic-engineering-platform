from pathlib import Path
import os, json
ws=Path.cwd()
print('CWD', ws)
print('Tree input:')
for p in sorted((ws/'input').glob('**/*')):
    print(p.relative_to(ws), p.stat().st_size)
manual=(ws/'input'/'quote_cli_manual.md')
print('\n--- quote_cli_manual.md ---')
print(manual.read_text(encoding='utf-8', errors='replace'))
