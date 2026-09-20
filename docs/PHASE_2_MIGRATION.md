# Phase 2 source inspection and disposition

Source: `dragon0816/telegram-local-agent`, commit
`4b40a215909e4fdd4b65519d70669a84e9abd43d` (read-only inspection).

| Source | Observed behavior | Decision and preserved boundary |
| --- | --- | --- |
| `core/task_router.py` | dot command -> ordered run/release/build regexes -> Ollama parsing; explicit command aliases; raw arguments; forwarding actor/files | ADAPT parsing and precedence, preserve source characterization cases; route intent without executing during selection |
| `core/skill_registry.py` | Markdown procedures plus frontmatter command mappings, ordered natural-language rules/defaults | ADAPT into typed Skill manifests with procedure text and explicit targets; runtime accepts validated data, no directory scanning |
| `core/tool_registry.py` | explicit TOOLS mappings; sync/async dispatch; filters kwargs; missing tools raise KeyError | ADAPT explicit installed mappings; typed async handlers and schema validation replace silent parameter dropping; no dynamic imports |
| `core/mcp_registry.py` | tools/list and tools/call; transport-specific code and configuration; errors often converted to strings/empty lists | WRAP an injected client with list_tools/call_tool; typed discovery failures; explicit host bindings; no credential-bearing configuration migration |
| `core/file_manager.py` | file_id, filename, path, size, MIME metadata; writes uploads and accepts existing paths | ADAPT metadata to opaque AttachmentRef; preserve context forwarding, defer upload/storage/path resolution |

## Characterization and intentional differences

`tests/fixtures/source_router.txt` is a verbatim line excerpt extracted from the pinned
source (stdlib imports, keyword table/detector, TaskRouter init/route/dot parser only).
It is test-only, not installed or imported by platform code. Tests inject inert Skill,
model and dispatch doubles; no source capability or external service executes.
The fixture's README records extraction and checksums. Regression cases run against
both the original excerpt and the adapted routing layer.

- Preserve matching order, case-insensitive keyword matching, command alias lookup,
  dot-command whitespace handling, raw args and actor/file context.
- Unknown explicit skills/commands fail closed as needs-input rather than LLM fallback
  or implicit function-name execution. Scoped target selection must be unambiguous.
  This includes dot-shaped messages: the source retried e.g. `build.package` against
  the keyword table after a failed skill lookup and could deterministically route it;
  the adaptation returns needs-input so an explicit-command-shaped typo can never
  silently select a different skill. Both behaviors are pinned by regression tests.
- No fuzzy selection across namespaces or versions. Install a specific alias per namespace.
- Do not guess `path`, `url` or `query` from raw arguments, silently drop unexpected
  parameters, or copy config/user dictionaries into tool arguments. Host-provided
  typed context carries actor/files; typed input validation reports invalid arguments.
- Deterministic paths never call a model, including result summarization. The source
  can summarize deterministic tool results with Ollama; that is deliberately omitted.
- A host policy grant, input validation and explicit execution approval (when required)
  are checked at every dispatch, including MCP. No publication/review bypass exists.
- Provider and transport implementations, source production tools (except
  `tools/file_tools.py::read_file`, adapted below), HTML channel output,
  reload/config discovery and file persistence are not migrated or deprecated.

## First production tool adaptation — `tools/file_tools.py::read_file`

Decision: ADAPT into `src/capabilities/files.py` as the read-only
`filesystem/read-file` capability dispatched through the shared Bridge policy path
(default-deny grant with permissions, policy reference and execution approval
reference). `tests/fixtures/source_file_tools.txt` pins a verbatim excerpt (imports,
`read_file`, `_fmt_size`, `_extract_path`); the fixtures README records full-source
and excerpt checksums. Regression tests compare adapter outcomes against the pinned
source oracle on the same files.

Preserved: the source check order (existence, file kind, extension allowlist,
500 KB size cap), the exact encoding fallback chain (`utf-8`, `utf-8-sig`, `big5`,
`gbk`, `latin-1`) and `max_lines` truncation. Informative non-crash outcomes remain
results, adapted from channel strings to a typed outcome enum. The terminal latin-1
fallback decodes any byte sequence, so the source's undecodable branch is unreachable
and has no adapted outcome.

Intentional differences: no `_extract_path` natural-language path guessing (an
explicit validated `path` is required), no HTML/emoji channel formatting, no silent
`**kwargs` acceptance, and unexpected OS errors surface as the typed `handler_error`
failure without exception text. The remaining `file_tools` functions and other
production tool modules are not migrated by this slice.

Rollback: remove the new routing/dispatch modules and retain Phase 1 contracts. Source
repositories remain untouched. These changes do not establish full production parity.
