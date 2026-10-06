from pathlib import Path
base=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
print('workspace files:')
for p in Path('.').rglob('*'):
    if p.is_file(): print(p)
print('\nnearby names containing expense/data/csv/json/db (max 100):')
count=0
for p in base.rglob('*'):
    if count>=100: break
    low=p.name.lower()
    if any(s in low for s in ['expense','data','.csv','.json','.db','.sqlite']):
        print(p, 'dir' if p.is_dir() else p.stat().st_size)
        count+=1
print('count listed', count)
