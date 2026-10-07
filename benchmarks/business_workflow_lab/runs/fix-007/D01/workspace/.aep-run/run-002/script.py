from pathlib import Path
print((Path.cwd()/'input'/'expense_manual.md').read_text(encoding='utf-8'))