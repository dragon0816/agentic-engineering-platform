# Small local Knowledge Vault validation (2026-10-02)

The owner selected an independent test Vault for the first validation. No
content from `RS_Knowledge` was copied, ingested or sent to a model. The
source tree remains unchanged. The later enterprise Vault conversion needs a
separate plan because its root lacks the platform-required `index.md` and
`log.md`; the owner will identify a queryable subset before model use.

A copy of the repository's synthetic company-Agent validation Vault is at
`.scratch/knowledge-validation/vault`. The matching exact published fixture
manifest is `.scratch/knowledge-validation/manifest.json`. A separate Host
configuration and workspace are under `.scratch/knowledge-validation/`, leaving
the installed preview Host untouched. The copied manifest retains the fixture
review/evaluation evidence and pins the copied Vault's absolute path; its Raw,
decision and content hashes were checked by `KnowledgeCatalog.register`.

Observed local checks:

- Catalog registration succeeded for `validation/company-agent-guide@1.0.0`.
- Static lint inspected two wiki pages and reported `clean=true`; the Vault
  contains one Raw file and two wiki files.
- A temporary loopback Agent Web instance using the isolated Host returned
  HTTP 200 from `/api/assets` with exactly this Knowledge identity, then shut
  down.
- Four focused integration tests passed for grounded asking, citation
  preservation, Bridge policy refusal, governed improvement and rejection of
  unsupported wiki-only claims. Those tests use a scripted model.

The isolated Host doctor says the local Host is ready but its resident Agent
is pending in the Codex process because `LITELLM_MASTER_KEY` is not set there.
No live Gateway Knowledge answer was claimed. The owner may run Agent Web with
the isolated configuration after setting the existing key in the launching
shell; the configuration contains an environment-variable reference, never a
credential value. This proof does not exercise `/wiki-convert`,
`/wiki-ingest` or `/wiki-lint` as installed Workflows; those are separate
integration work.
