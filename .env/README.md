# Local developer credentials

This directory provides an explicit, machine-local way to give development
commands the credentials they need. The real file is ignored by Git. Each
developer and computer uses its own values.

Create the file on the development computer:

```powershell
Copy-Item .env\example.yaml .env\local.yaml
notepad .env\local.yaml
```

Load it into the current PowerShell process before running `gh` or local tools:

```powershell
. .\scripts\import-local-env.ps1
gh api user --jq .login
gh auth status --hostname github.com
```

The file is a deliberately small YAML subset: one `NAME: "value"` mapping per
line, with no nesting, lists, aliases or executable content. The loader accepts
only these names and ignores allowed entries whose values remain empty:

| Name | Used for |
|---|---|
| `GH_TOKEN` | GitHub CLI and GitHub API operations from this shell |
| `OPENAI_API_KEY` | Direct local OpenAI API development; GitHub Actions still uses the repository secret |
| `AEP_GITHUB_TOKEN` | AEP's local GitHub Projects integration |

The file is plaintext on this computer even though Git ignores it. Keep it only
on a trusted development computer, never put it on a shared test workstation,
and use a separate token per person and computer. Revoke that token when the
computer is retired or lost.

For `GH_TOKEN`, prefer a fine-grained personal access token limited to this
repository. Grant only the operations the developer needs. Normal development
usually needs Contents, Pull requests, Issues and Actions; use read-only or
read/write for each according to the work. Add Workflows only when editing
workflow files, and Variables or Secrets only when managing those settings.
Repository secrets remain the right place for GitHub Actions credentials.

The loader does not run automatically, persist values outside the current
process, print secret values, or make runtime code discover local YAML files.
