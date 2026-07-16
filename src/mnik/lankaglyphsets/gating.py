"""Back-compat shim: gating moved to validation.py (dependency analysis).

The presence-gate semantics are unchanged; the report is now a full
ValidationReport (aliased to GateReport here) that records *which* glyphs
blocked which rules instead of only counts.
"""

from __future__ import annotations

from .validation import (  # noqa: F401
    GateReport,
    ValidationReport,
    analyze,
    gate,
    summarize,
)
