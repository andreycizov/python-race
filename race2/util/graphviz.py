import os

from dataclasses import dataclass

from race2.abstract import Visitor, ExecutionState, SpecialState


@dataclass
class ReprStr:
    inner: str

    def __repr__(self):
        return self.inner


def graphviz(
        visitor: Visitor,
        process_id_map: dict[int, str] | None = None,
        filename: str = "/home/andrey/Downloads/test.gv",
        should_view: bool = True,
):
    print("buildng graphviz")
    from graphviz import Source

    process_id_map = process_id_map or {}

    vertices: dict[ExecutionState, int] = {
        k: v
        for v, k in enumerate(
            set(
                y for (v1, _), v2_dict in visitor.visited_edges.items()
                for v2 in v2_dict.keys()
                for y in [(v1), (v2)]
            )
        )
    }

    vertices_str = "\n".join(
        f'{index} [label="{vertex}"]'
        for state, index in vertices.items()
        for vertex in [
            "("
            + " ".join(
                f"{render_process_id}:{render_process_state_id}"
                for process_id, process_state_id in sorted(state.states.items())
                for render_process_state_id in [
                    ReprStr(process_state_id.name[:1])
                    if isinstance(process_state_id, SpecialState)
                    else process_state_id
                ]
                for render_process_id in [process_id_map.get(process_id, process_id)]
            )
            + ")"
        ]
    )

    edges = [
        (vertices[v1], vertices[v2], x) for (v1, x), v2_dict in visitor.visited_edges.items()
        for v2 in v2_dict.keys()
    ]

    edges_str = "\n".join(
        f'{vertex_a} -> {vertex_b} [label="{render_process_label}"]'
        for vertex_a, vertex_b, process_id in edges
        for render_process_label in [process_id_map.get(process_id, process_id)]
    )

    temp = f"""
    digraph G{{
    edge [dir=forward]
    node [shape=plaintext]

    {vertices_str}
    {edges_str}
    }}
    """

    with open("/home/andrey/Downloads/gv.dot", "w+") as file_obj:
        file_obj.write(temp)

    # print(temp)
    print("rendering")

    # return

    s = Source(temp, filename=filename, format="png")
    if should_view:
        s.view()
        import time

        time.sleep(5)
        os.unlink(filename)
    else:
        s.render(view=False, outfile=filename)
