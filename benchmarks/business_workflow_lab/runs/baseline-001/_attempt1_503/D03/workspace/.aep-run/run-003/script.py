from pathlib import Path
root=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
print('root exists', root.exists())
for p in root.glob('expense_desktop_mock/*'):
    print(p, p.stat().st_size)
