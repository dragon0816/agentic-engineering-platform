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

## Pinned file-tool characterization

Same source commit. File: `tools/file_tools.py`. UTF-8, LF-normalized full source
SHA-256:
`3cb4a33247476611172bf6c72c9306425eb1fe1484d1701b5ef38206b903777e`.

`source_file_tools.txt` retains verbatim source lines for the top-level imports and
the `read_file`, `_fmt_size` and `_extract_path` functions. Other functions and the
`TOOLS` table are excluded. Excerpt SHA-256 (UTF-8/LF):
`75bc3346d85961d68e700266842f54b80776c811d8e9616df260aba6586aa154`.
No formatting or implementation edits should be applied to the excerpt.

Unlike the routing oracle, `read_file` characterization exercises the excerpt against
pytest-managed temporary files; it performs no writes outside the test directory.

## Pinned job-runner characterization

Source commit: `dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43`.
File: `host-bridge/app/services/jobrunner.py`. UTF-8, LF-normalized full source
SHA-256:
`a40b112986744df5b1ea01535c2b64aec2b15083f97abe94802fa524291c7baa`.

`source_jobrunner.txt` retains verbatim source lines for the stdlib imports, the
module logger and run limits, `_now`, `Caller`, `JobRun`, `JobRegistry`,
`_job_callable`, `run_sync`, `run_async` and `get_run`. Discovery, step-table,
x-ui, options, telemetry and publishing helpers are excluded and replaced by inert
test doubles. Excerpt SHA-256 (UTF-8/LF):
`8f7edd5b111e0bd144d896c4c9c4a3468e4fa9baf81fa14eba62a24fdef9a399`.
No formatting or implementation edits should be applied to the excerpt.

The excerpt runs real (inert) callables on its own thread pool inside the tests;
no job module, network, ops dashboard or host capability is touched.

## Pinned step-table characterization

Same `rs_workflow_system` commit. File: `host-bridge/jobs/_steps.py`. UTF-8,
LF-normalized full source SHA-256:
`426713d63b954269b534d3182621a253e4c164b7b98af2b2e6e0276ad3428642`.

`source_steps.txt` retains the whole module verbatim except its module docstring
(source lines 1–39); it is self-contained stdlib code. Excerpt SHA-256 (UTF-8/LF):
`fb7e1e3754f4783dbf32edb93cf79698eff1d415ed6058487ff8eb3d4ec334a5`.
No formatting or implementation edits should be applied to the excerpt.

Tests attach a table and drive it with inert bodies; nothing outside the test
process is touched.
## Pinned n8n dispatch graph projection

Source: `dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43`,
`workflows/13_release_package.json`. Full source bytes SHA-256:
`8dfb7400cfa9c4ff9daa91ab2c66b853b13e6b03edbd7acab5061c76a94e540f`.

`source_n8n_release.json` retains the source graph's `connections`, HTTP node
name/type/method/jsonBody (and retryOnFail if present), and IF node name/type/
conditions. Values are copied without expression edits; JSON formatting is
normalized to UTF-8/LF, two-space indentation. Projection SHA-256:
`4135789e5a71efba67206f1729d73a0a47e44ef3e61f3855925630765d9e27a5`.
URLs, headers, parameter defaults, credentials and unrelated node UI properties
are excluded. Tests inspect this declarative graph; no JS expression or n8n node
is executed. This is a source-behavior reference, not an importable workflow.
