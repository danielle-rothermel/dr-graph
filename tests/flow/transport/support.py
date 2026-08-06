from dr_graph.flow.transport import TransportCell, TransportProblem


def cell(
    source_index: int,
    destination_index: int,
    *marginal_costs: int,
) -> TransportCell:
    return TransportCell(source_index, destination_index, marginal_costs)


def problem(
    supplies: tuple[int, ...],
    demands: tuple[int, ...],
    cells: tuple[TransportCell, ...],
) -> TransportProblem:
    return TransportProblem(supplies, demands, cells)
