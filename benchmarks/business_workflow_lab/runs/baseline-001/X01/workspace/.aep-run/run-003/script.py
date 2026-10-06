from pathlib import Path
root=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
for p in [root/'quote_cli_mock'/'run_quote_cli.py', root/'quote_cli_mock'/'quote_cli.cmd', root/'expense_desktop_mock'/'expense_app.py']:
    print('\n---', p, '---')
    txt=p.read_text(encoding='utf-8', errors='replace')
    print(txt[:12000])
