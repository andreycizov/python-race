import dataclasses
import itertools
from typing import Generic, TypeVar, Callable

ET = TypeVar("ET")
VT = TypeVar("VT")


@dataclasses.dataclass(slots=True)
class Graph(Generic[VT, ET]):
    v: list[int] = dataclasses.field(default_factory=list)
    e: list[tuple[int, int, int]] = dataclasses.field(default_factory=dict)
    v_labels: dict[int, VT] = dataclasses.field(default_factory=dict)
    e_labels: dict[int, ET] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        vertex_ids = set(self.v)
        for _, v1, v2 in self.e:
            assert v1 in vertex_ids and v2 in vertex_ids, (v1, v2, vertex_ids)

        for k in self.v_labels.keys():
            assert k in self.v, k

        edge_ids = set(x for x, _, _ in self.e)
        for k in self.e_labels.keys():
            assert k in edge_ids, (k, edge_ids)

    @classmethod
    def from_adjacency_list(
        cls,
        edges: list[tuple[int, int] | tuple[int, int, int]] = None,
        vertices: list[int] = None,
        v_labels: dict[int, VT] = None,
        e_labels: list[ET] = None,
    ) -> "Graph[VT, ET]":
        edges = edges or []
        vertices = vertices or []

        if e_labels is not None:
            assert len(e_labels) == len(edges)
        else:
            e_labels = []

        v_labels = v_labels or {}

        edges_list = [
            (index, v1, v2)
            for i, e_defn in enumerate(edges)
            for *_, dv1, dv2 in [e_defn]
            for index, v1, v2 in [e_defn if len(e_defn) == 3 else (i, dv1, dv2)]
        ]
        vertices_list = (
            list(set(x for _, a, b in edges_list for x in [a, b])) + vertices
        )

        assert all(k in vertices_list for k in v_labels.keys())

        return Graph(
            v=vertices_list,
            e=edges_list,
            v_labels=v_labels,
            e_labels={k: v for v, (k, _, _) in zip(e_labels, edges_list)},
        )

    def copy(self) -> "Graph[VT, ET]":
        return Graph(
            v=list(self.v),
            e=list(self.e),
            v_labels=dict(self.v_labels),
            e_labels=dict(self.e_labels),
        )

    def adjacency_dict(self) -> dict[int, list[int, int]]:
        return {
            v1: [(e, v2) for e, _, v2 in v2s]
            for v1, v2s in itertools.groupby(
                sorted(self.e, key=lambda x: x[1]), lambda x: x[1]
            )
        }

    def reverse(self) -> "Graph[VT, ET]":
        return dataclasses.replace(self, e=[(idx, v2, v1) for idx, v1, v2 in self.e])

    def vertex_next_id(self) -> int:
        return max(self.v) + 1

    def edge_next_id(self) -> int:
        return max(x for x, _, _ in self.e) + 1

    def subset(self, v: list[int]) -> "Graph[VT, ET]":
        # this is not exactly true, as the outgoing edges may go into vertices not in the lst of gives vertices
        e = [(e, v1, v2) for e, v1, v2 in self.e if v1 in v and v2 in v]
        return dataclasses.replace(
            self,
            v=[x for x in self.v if x in v],
            e=e,
            v_labels={k: v for k, v in self.v_labels if k in v},
            e_labels={k: v for k, v in self.e_labels if k in [x for x, _, _ in e]},
        )

    def union(self, other: "Graph[VT, ET]") -> "Graph[VT, ET]":
        # fix later as this requires relabeling the edges
        assert set() == set(x for x, _, _ in self.e) & set(x for x, _, _ in other.e)
        return dataclasses.replace(
            self,
            v=list(set(self.v) | set(other.v)),
            e=self.e + other.e,
            v_labels={**self.v_labels, **other.v_labels},
            e_labels={**self.e_labels, **other.e_labels},
        )

    def graphviz(self) -> str:
        vertices_str = "\n".join(
            f'{vertex_idx} [label="{vertex_label}"]'
            for vertex_idx in self.v
            for vertex_label in [self.v_labels.get(vertex_idx, vertex_idx)]
        )

        edges_str = "\n".join(
            f'{v1} -> {v2} [label="{edge_label}"]'
            for edge_idx, v1, v2 in self.e
            for edge_label in [self.e_labels.get(edge_idx, "")]
        )

        return f"""
        digraph G{{
        edge [dir=forward]
        node [shape=plaintext]

        {vertices_str}
        {edges_str}
        }}
        """

    def graphviz_render(self, filename="temp.gv") -> None:
        from graphviz import Source

        s = Source(self.graphviz(), filename=filename, format="png")
        s.view()
        import os

        os.unlink(filename)

    def map(
        self,
        v: Callable[[int], int | None] = None,
        e: Callable[[int, int, int], tuple[int, int, int] | None] = None,
    ) -> "Graph[VT, ET]":
        new_v = [
            new_x for x in self.v for new_x in [v(x) if v else x] if new_x is not None
        ]

        if e is None:
            e = (
                lambda idx, v1, v2: (idx, v1, v2)
                if v1 in new_v and v2 in new_v
                else None
            )

        new_e = [
            new_x
            for idx, v1, v2 in self.e
            for new_x in [e(idx, v1, v2) if e else (idx, v1, v2)]
            if new_x is not None
        ]

        new_v_ids = set(x for x in new_v)
        new_e_ids = set(x for x, _, _ in new_e)

        new_v_labels = {k: v for k, v in self.v_labels.items() if k in new_v_ids}
        new_e_labels = {k: v for k, v in self.e_labels.items() if k in new_e_ids}

        return dataclasses.replace(
            self, v=new_v, e=new_e, v_labels=new_v_labels, e_labels=new_e_labels
        )
