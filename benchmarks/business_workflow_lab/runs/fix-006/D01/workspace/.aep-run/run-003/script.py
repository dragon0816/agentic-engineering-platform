from pathlib import Path
text=(Path.cwd()/'input'/'expense_manual.md').read_text(encoding='utf-8')
print(text)