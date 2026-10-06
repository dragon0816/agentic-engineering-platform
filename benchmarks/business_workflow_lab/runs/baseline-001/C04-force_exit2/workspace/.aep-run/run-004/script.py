from pathlib import Path
base=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock')
for p in sorted(base.glob('quote_cli/**/*.py')):
    print('\n---', p.relative_to(base), '---')
    txt=p.read_text(encoding='utf-8', errors='replace')
    print(txt[:6000])
