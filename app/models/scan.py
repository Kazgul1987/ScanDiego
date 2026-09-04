from __future__ import annotations

from enum import StrEnum


class ScanStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"

