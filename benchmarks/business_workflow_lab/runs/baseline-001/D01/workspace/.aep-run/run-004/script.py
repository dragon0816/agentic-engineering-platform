from pathlib import Path
app=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\expense_desktop_mock\expense_app.py')
txt=app.read_text(encoding='utf-8')
for i,line in enumerate(txt.splitlines(),1):
    if 'def query' in line or 'def filtered' in line or 'def export' in line or 'def write_' in line:
        print('\n--- around', i, line, '---')
        lines=txt.splitlines()
        for j in range(max(1,i-10), min(len(lines), i+90)+1): print(f'{j:04d}: {lines[j-1]}')
