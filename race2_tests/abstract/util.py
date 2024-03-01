from dataclasses import dataclass

from race2.abstract import Visitor, ExecutionState, SpecialState


@dataclass
class ReprStr:
    inner: str

    def __repr__(self):
        return self.inner


def graphviz(visitor: Visitor):
    from graphviz import Source

    vertices: dict[ExecutionState, int] = {
        k: v
        for v, k in enumerate(
            set(
                y for (v1, _), v2 in visitor.visited_edges.items() for y in [(v1), (v2)]
            )
        )
    }

    vertices_str = "\n".join(
        f'{index} [label="{vertex}"]'
        for state, index in vertices.items()
        for vertex in [
            "("
            + " ".join(
                f"{k}:{v2}"
                for k, v in sorted(state.states.items())
                for v2 in [ReprStr(v.name) if isinstance(v, SpecialState) else v]
            )
            + ")"
        ]
    )

    edges = [
        (vertices[v1], vertices[v2], x) for (v1, x), v2 in visitor.visited_edges.items()
    ]

    edges_str = "\n".join(
        f'{vertex_a} -> {vertex_b} [label="{x}"]' for vertex_a, vertex_b, x in edges
    )

    temp = f"""
    digraph G{{
    edge [dir=forward]
    node [shape=plaintext]

    {vertices_str}
    {edges_str}
    }}
    """

    # print(temp)

    s = Source(temp, filename="/home/andrey/Downloads/test.gv", format="png")
    s.view()
