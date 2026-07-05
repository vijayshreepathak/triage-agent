"""Tool-layer error types."""

from __future__ import annotations


class ToolConfigurationError(Exception):
    """A provider was selected but its configuration is incomplete.

    Raised at composition time (app startup / first wiring), never
    mid-request — misconfiguration must fail fast and loudly.
    """
