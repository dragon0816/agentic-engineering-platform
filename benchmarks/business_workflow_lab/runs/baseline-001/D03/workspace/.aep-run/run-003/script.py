from pathlib import Path
app=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\expense_desktop_mock\expense_app.py')
print(app.exists(), app)
if app.exists():
    txt=app.read_text(encoding='utf-8', errors='replace')
    print(txt[:5000])
    print('len', len(txt))
    # list dir
    for p in app.parent.iterdir(): print(p.name, p.stat().st_size if p.is_file() else 'dir')
