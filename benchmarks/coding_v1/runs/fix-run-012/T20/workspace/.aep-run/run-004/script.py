from pathlib import Path
import json
ws=Path.cwd()
p=ws/'input'/'manifest.json'
print(p.read_text(encoding='utf-8'))
