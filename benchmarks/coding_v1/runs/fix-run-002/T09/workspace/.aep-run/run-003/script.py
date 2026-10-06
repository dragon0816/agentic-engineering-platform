from pathlib import Path
base=Path.cwd()
repo=next(p for p in [base,*base.parents] if (p/'pyproject.toml').exists())
queries=['E2E_02_SOP_WORKFLOW.md','test_product_e2e_02.py','workflow.proof','SOP','draft Workflow','runtime']
for rel in ['docs/phases/E2E_02_SOP_WORKFLOW.md','tests/test_product_e2e_02.py']:
    f=repo/rel
    print('\n===== ',rel, f.exists(),'=====')
    if f.exists(): print(f.read_text(encoding='utf-8', errors='replace')[:12000])
print('\nExamples tree snippets:')
for d in ['examples','tasks','skills','packages','src/workflow']:
    p=repo/d
    if p.exists():
        for x in sorted(p.rglob('*'))[:200]:
            if x.is_file() and x.suffix in ['.json','.yaml','.yml','.md','.py']:
                print(x.relative_to(repo))
