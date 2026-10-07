from pathlib import Path
ws=Path.cwd()
manual=ws/'input'/'quote_cli_manual.md'
print('manual exists:', manual.exists())
if manual.exists():
    text=manual.read_text(encoding='utf-8', errors='replace')
    print(text[:4000])
