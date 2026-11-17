"""Synthetic worker that exits before answering anything. Activation must
fail truthfully and leave nothing registered."""

import sys

sys.exit(3)
