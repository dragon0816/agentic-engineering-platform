# Feature plugin v1 golden fixture

Frozen evidence for plugin package/workspace compatibility before any schema
extension. Synthetic data only; no customer files, C4C or BI data.

- `hello.aep-plugin.v1.json`: exact bytes of `examples/plugins/hello.aep-plugin.json`
  at core source revision `a0496ae0`.
  sha256 `2fd27dd8799602e19ed29a7c79ad2f56469b01021a9618daab8d6f2642897413`,
  package `content_sha256` `4bb06aca80372e299de4cf34e08411fab696d0d13a2cdb774ec67b8285956d2d`.
- `golden-workspace.v1.json`: every file the unchanged `a0496ae0` `PluginManager`
  wrote when it installed that package into a fresh synthetic workspace
  (origin actor `fixture-owner`, channel `compatibility-fixture`), captured after
  the worker processes were closed. Each entry is a workspace-relative path with
  its sha256, size and base64 bytes: the ledger, the staged package and worker,
  the owned Skill/Workflow assets, the bundle asset ledger and the data marker.
  The ledger was produced by the real install, not written by hand, and holds no
  absolute paths, so it can be materialized into any new workspace.

Tests (`tests/test_plugin_v1_compatibility.py`) assert these hashes explicitly,
reinstall the package, and restore the materialized workspace with the current
manager without recalculating anything from future schemas. Regenerating this
fixture is a deliberate compatibility decision, not a routine update.
