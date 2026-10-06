from pathlib import Path
base=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock')
print(base.exists(), list(base.glob('*')))
for p in base.glob('*'):
    print('\n---',p,'---')
    if p.is_file() and p.suffix in ['.py','.cmd','.json','.csv']:
        txt=p.read_text(encoding='utf-8', errors='replace')
        print(txt[:3000])
