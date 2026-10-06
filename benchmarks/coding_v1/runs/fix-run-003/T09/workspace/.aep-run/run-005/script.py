from pathlib import Path
repo=Path('../../../../..').resolve().parent
files=['docs/CONTRACTS.md','docs/WORKFLOW_CHECKPOINTS.md','docs/ARCHITECTURE.md','tests/test_engine.py','tests/test_gateway_task_execution.py','tests/test_run_python.py','README.md']
for f in files:
    p=repo/f
    print('\n===== ', f, '=====')
    txt=p.read_text(encoding='utf-8', errors='replace')
    # print relevant snippets around 'workflow'
    low=txt.lower()
    idx=0; shown=0
    while True:
        i=low.find('workflow', idx)
        if i<0 or shown>=5: break
        print(txt[max(0,i-1200):i+2500])
        print('\n---SNIP---')
        idx=i+1; shown+=1