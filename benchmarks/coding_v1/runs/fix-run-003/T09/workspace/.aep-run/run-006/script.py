from pathlib import Path
repo=Path('../../../../..').resolve().parent
for f in ['docs/phases/E2E_02_SOP_WORKFLOW.md','tests/test_product_e2e_02.py','src' ]:
    p=repo/f
    print('\n===== ', f, '=====')
    if p.is_file():
        txt=p.read_text(encoding='utf-8', errors='replace')
        print(txt[:20000])
    else:
        print('dir exists', p.exists())