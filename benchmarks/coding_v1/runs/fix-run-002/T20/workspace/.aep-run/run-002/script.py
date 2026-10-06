from pathlib import Path
ws=Path.cwd()
for rel in ['input/manifest.json','input/data/test_results.csv']:
    p=ws/rel
    print(f'--- {rel} ---')
    print(p.read_text(encoding='utf-8-sig'))
