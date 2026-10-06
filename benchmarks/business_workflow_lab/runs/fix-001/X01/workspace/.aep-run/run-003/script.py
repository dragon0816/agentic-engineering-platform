from pathlib import Path
base=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
print('top-level in lab:')
for p in sorted(base.iterdir()):
    print(p.name, 'dir' if p.is_dir() else p.stat().st_size)
print('\nsearch expense-ish/quote/sap files (limited):')
for pat in ['*expense*','*Expense*','*.db','*.csv','*.json','*.xlsx','*.py','*.cmd']:
    print('\nPAT',pat)
    c=0
    for p in base.rglob(pat):
        try:
            print(p.relative_to(base), 'dir' if p.is_dir() else p.stat().st_size)
            c+=1
            if c>=50: break
        except Exception as e: pass
