# Company Bridge agent integration v1

This bounded integration restores the three routes that a Company Bridge must
make available to the Personal Agent.  It does not install or publish a
candidate, grant a capability, or contact a production system.

## Installed routes

After updating the host bundle, export the shipped assets into the Bridge
workspace.  The routes are explicit dot commands, so they bypass model intent
selection:

| Command | Target | Result |
| --- | --- | --- |
| `workflow.draft {…}` | `workflow-author/draft@1.0.0` | Candidate Workflow in `draft` lifecycle only |
| `knowledge.ask {…}` | `knowledge-query/ask@1.0.0` | Grounded answer from one exact published Knowledge version |
| `personal.proof <fixture-path>` | `company-agent/personal-proof@1.0.0` | Traceable local read-only proof workflow |

The JSON object form is used only when the target capability has structured
input.  It is decoded locally and then validated against the capability input
contract; malformed JSON is refused as `invalid_command_json`.

## SOP PDF route

`workflow.draft` accepts exactly one of `sop` or `sop_pdf_path`.  A PDF must
be below the configured `workspace_root`, have a `.pdf` suffix, and be
readable through the optional `office` package.  A read failure returns the
closed `sop_unreadable` draft result.  The source PDF is never copied into a
Registry asset.  A successful result remains a candidate and is never run,
installed, or published by this route.

## Knowledge binding

`host.json` declares every Knowledge version that the host may query:

```json
"knowledge": [{
  "asset": {"namespace": "engineering", "name": "widget-guide", "version": "1.0.0"},
  "vault_root": "C:\\AEP\\workspace\\knowledge\\widget-guide-v1"
}]
```

The matching manifest must be under `assets/knowledge`, must be published,
and its Raw, decision and content digests must match the local Vault.  The
binding cannot use `latest`; it always names an exact scoped asset version.
Knowledge querying also requires the existing configured model binding because
the returned answer must be grounded by Raw citations.

## Required grants

Installation is not authorization.  The Bridge must separately grant the
bound actor the policy requirements for `workflow-author.draft` and
`knowledge-query.ask` before those routes can run.

The `personal.proof` deployment profile does **not** grant the general
`filesystem/read-file` capability. It uses the distinct
`company-agent/personal-proof-fixture-read@1.0.0` capability, wired only to:

```text
<workspace>\hermes-fixtures\personal-proof\
```

The fixed test profile may grant only this asset to the bound test actor, with
`filesystem.read` permission and `personal-proof-fixture-read-policy`. A
grant cannot read another workspace file because the handler resolves paths
under that fixture root before it opens them. It has no central dependency.

## Hermes verification profile

Hermes should rebuild the exact PR SHA and collect these three independent
evidence records before marking a validation passed:

1. A controlled local SOP PDF produces a `draft` candidate; no workflow is
   installed, published, or executed.
2. A question to the configured exact Knowledge asset returns Raw citations
   and the requested asset identity/version.
3. `personal.proof` runs the installed proof workflow over a controlled local
   fixture and records its trace and succeeded run.

If a route is absent, an asset/grant/model/Vault prerequisite is missing, or
the PDF cannot be read, Hermes must attach sanitized evidence to the existing
Issue.  It must not mark the profile passed.
