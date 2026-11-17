"""Shared-platform control-plane reference services."""

from plugins.in_process import ensure_bundled_importable

# The platform reads BI dataset snapshots with BI Knowledge's own reader
# (`control_plane.bi_datasets`). BI ships as a feature plugin beside AEP, not in
# the core package (Plugin API 1.2), so its bundled folder goes on the path here.
ensure_bundled_importable()
