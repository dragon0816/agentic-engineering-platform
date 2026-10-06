from pathlib import Path
Path('output/probe.txt').parent.mkdir(exist_ok=True)
Path('output/probe.txt').write_text('probe', encoding='utf-8')
