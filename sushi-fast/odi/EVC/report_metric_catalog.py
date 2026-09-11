"""Compatibility alias for the active report implementation."""

import sys

from .report_v2 import report_metric_catalog as _implementation

sys.modules[__name__] = _implementation
