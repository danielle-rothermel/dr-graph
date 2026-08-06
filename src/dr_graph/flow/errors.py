class FlowError(Exception):
    pass


class FlowProblemError(FlowError, ValueError):
    pass


class InfeasibleFlowError(FlowError):
    pass


class FlowPostconditionError(FlowError):
    pass
