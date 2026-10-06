from pathlib import Path
base=Path.cwd(); repo=next(p for p in [base,*base.parents] if (p/'pyproject.toml').exists())
for rel in ['src/workflow/engine.py','src/workflow/dispatch.py','src/workflow/payloads.py','src/workflow/proof.py','src/capabilities/registry.py','packages/rs-workflow-system/w90-bundle-smoke/workflow.json','examples/default-marketplace/candidates/engineering__jira-weekly-report-preview__1.0.0.json','tests/fixtures/e2e_02/sop-workflow.json']:
 f=repo/rel; print('\n===== '+rel+' =====')
 txt=f.read_text(encoding='utf-8', errors='replace')
 print(txt[:20000])
