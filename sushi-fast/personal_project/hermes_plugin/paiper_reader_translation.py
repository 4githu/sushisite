"""Compatibility import for the packaged Paiper Reader Hermes plugin."""

from personal_project.reader_translation.hermes_plugin import LLM_PURPOSE, register
from personal_project.reader_translation.hermes_plugin import _handle as _handle_translation

import sys

__all__ = ["LLM_PURPOSE", "register", "_handle_translation", "sys"]
