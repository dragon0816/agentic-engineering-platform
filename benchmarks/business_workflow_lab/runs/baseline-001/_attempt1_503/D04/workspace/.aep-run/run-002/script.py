from pathlib import Path
app=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\expense_desktop_mock\expense_app.py')
print('exists', app.exists(), app)
if app.exists():
    txt=app.read_text(encoding='utf-8')
    print(txt[:8000])