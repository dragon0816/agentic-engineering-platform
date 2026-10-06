from pathlib import Path
app=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\expense_desktop_mock')
print('exists', app.exists())
if app.exists():
    for p in sorted(app.glob('**/*')):
        print(p, p.stat().st_size if p.is_file() else 'DIR')
    f=app/'expense_app.py'
    if f.exists():
        txt=f.read_text(encoding='utf-8')
        print('\n--- expense_app.py first 12000 ---')
        print(txt[:12000])
