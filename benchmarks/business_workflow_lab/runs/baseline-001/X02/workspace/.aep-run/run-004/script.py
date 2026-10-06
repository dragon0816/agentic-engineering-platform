from pathlib import Path
root=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
for f in [root/'quote_cli_mock'/'quote_cli'/'cli.py', root/'expense_desktop_mock'/'expense_app.py']:
    print('\n---', f, '---')
    txt=f.read_text(encoding='utf-8')
    print(txt[:12000])
