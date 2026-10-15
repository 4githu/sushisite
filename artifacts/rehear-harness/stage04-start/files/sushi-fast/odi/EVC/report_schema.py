"""Compatibility alias for the active report implementation."""

import sys

from .report_v2 import report_schema as _implementation

sys.modules[__name__] = _implementation
