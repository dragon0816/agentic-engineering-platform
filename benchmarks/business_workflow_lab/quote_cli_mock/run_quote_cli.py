"""Cross-platform launcher: python quote_cli_mock/run_quote_cli.py --help"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quote_cli.cli import main  # noqa: E402

raise SystemExit(main())
