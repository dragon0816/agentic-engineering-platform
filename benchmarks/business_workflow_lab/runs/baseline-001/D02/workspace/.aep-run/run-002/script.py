from pathlib import Path
app_dir=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\expense_desktop_mock')
print('exists', app_dir.exists())
if app_dir.exists():
    for p in app_dir.rglob('*'):
        print(p)
        if p.is_file() and p.suffix.lower() in ['.py','.csv','.json','.db','.sqlite','.xlsx','.md']:
            try:
                print('---',p.name,'---')
                print(p.read_text(encoding='utf-8')[:2000])
            except Exception as e: print('read err', e)
