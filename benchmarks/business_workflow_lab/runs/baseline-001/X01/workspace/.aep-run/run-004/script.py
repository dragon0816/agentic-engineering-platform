from pathlib import Path
root=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
for p in [root/'quote_cli_mock'/'run_quote_cli.py', root/'quote_cli_mock'/'quote_cli.cmd']:
    print('\n---', p, '---')
    print(p.read_text(encoding='utf-8', errors='replace'))
# source keys only
p=root/'operator'/'data'/'source.json'
print('\nsource exists',p.exists(), p.stat().st_size if p.exists() else None)
print(p.read_text(encoding='utf-8', errors='replace')[:2000])
