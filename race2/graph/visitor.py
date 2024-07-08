from race2.abstract import Visitor, ExecutionState, ProcessID, SpecialState
from race2.graph.abstract import Graph
from race2.graph.algorithm import Cycle
from race2.util.graphviz import ReprStr


def graph_from_visitor(vis: Visitor) -> Graph[ExecutionState, ProcessID]:
    vertices = {
        state: index
        for index, state in enumerate(
            set(y for (v1, _), v2 in vis.visited_edges.items() for y in [v1, v2])
        )
    }

    graph = Graph.from_adjacency_list(
        [(vertices[v1], vertices[v2]) for (v1, _), v2 in vis.visited_edges.items()],
        v_labels={index: state for state, index in vertices.items()},
        e_labels=[process_id for (_, process_id), _ in vis.visited_edges.items()],
    )

    return graph


def graph_render_labels(
    graph: Graph[ExecutionState | Cycle[ExecutionState, ProcessID], ProcessID],
    process_id_map: dict[ProcessID, str] = None,
) -> Graph[str, str]:
    graph = graph.copy()
    graph.e_labels = {k: str(v) for k, v in graph.e_labels.items()}
    if process_id_map is None:
        process_id_map = {}

    def map_vertex_label(
        label: ExecutionState | Cycle[ExecutionState, ProcessID]
    ) -> str:
        match label:
            case ExecutionState():
                return (
                    "("
                    + " ".join(
                        f"{render_process_id}:{render_process_state_id}"
                        for process_id, process_state_id in sorted(label.states.items())
                        for render_process_state_id in [
                            ReprStr(process_state_id.name[:1])
                            if isinstance(process_state_id, SpecialState)
                            else process_state_id
                        ]
                        for render_process_id in [
                            process_id_map.get(process_id, process_id)
                        ]
                    )
                    + ")"
                )
            case Cycle():
                return f"Cycle({len(label.sub_graph.v)},{len(label.cycle)})"
            case _:
                raise AssertionError(label)

    graph.v_labels = {k: map_vertex_label(v) for k, v in graph.v_labels.items()}
    return graph
