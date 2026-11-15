#!/usr/bin/env python3
"""Compatibility wrapper delegating to diy/toolshear_diy.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import toolshear_diy  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(toolshear_diy.main())
