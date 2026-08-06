from dr_graph.flow.errors import FlowError


class InfeasibleTransportError(FlowError):
    """Raised when a valid transport problem cannot satisfy all demand."""
