from __future__ import annotations


class FlowError(Exception):
    """Base exception for min-cost flow errors."""


class FlowProblemError(FlowError, ValueError):
    """Raised when a flow problem violates the public contract."""


class InfeasibleFlowError(FlowError):
    """Raised when the network cannot carry the exact required flow."""


class FlowPostconditionError(FlowError):
    """Raised when a solver result violates the flow contract."""
