# Pinned routing characterization

Source commit: `dragon0816/telegram-local-agent@4b40a215909e4fdd4b65519d70669a84e9abd43d`.
File: `core/task_router.py`. Retrieved using GitHub contents API with that exact ref.
UTF-8, LF-normalized full source SHA-256:
`07962ec932c5e4e07d0bf1b7fc1fb9df187ec9cce9d3dde4b41045338067ff54`.

`source_router.txt` retains verbatim source lines for top-level imports, assignments,
functions, and TaskRouter's `__init__`, `route`, `_try_dot_command`. Other methods are
excluded and replaced by inert test doubles. Excerpt SHA-256 (UTF-8/LF):
`dcbd706da14d43a1168fb4eaa068aee794186f4e94de8c9c01cac8c94b514cb3`.
No formatting or implementation edits should be applied to the excerpt.

The source excerpt is an offline characterization oracle, not a runtime dependency.
Test doubles intercept dispatch before any capability, network, file or model executes.
`routing_cases.json` is the shared source/adapted regression and evaluation corpus.
