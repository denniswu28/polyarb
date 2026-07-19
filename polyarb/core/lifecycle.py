"""Shared lifecycle states for research, simulation, and reporting records."""

from enum import Enum


class LifecycleState(str, Enum):
    """State names that must not be treated as interchangeable."""

    DETECTED = "detected"
    APPROVED = "approved"
    SIMULATED = "simulated"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    SETTLED = "settled"
    REPORTED = "reported"
