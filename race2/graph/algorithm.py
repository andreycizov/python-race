import dataclasses
import itertools
from collections import deque
from typing import Generic, Iterator, Set, Deque

from race2.graph.abstract import Graph, VT, ET


def collect_cycles(graph: Graph[VT, ET]) -> Iterator[list[int]]:
    for x in tarjan(graph):
        if len(x) > 1:
            yield x
    return
    root_queue = set(graph.v)

    adjacency_dict = graph.adjacency_dict()

    visited_cycles: Set[tuple[int, int]] = set()

    while len(root_queue):
        curr_root = root_queue.pop()

        queue: Deque[list[int]] = deque()
        queue.append([curr_root])

        visited: Set[int] = set()

        while len(queue):
            curr_path = queue.popleft()

            if curr_path[-1] in root_queue:
                root_queue.remove(curr_path[-1])

            if curr_path[-1] in curr_path[:-1]:
                index = curr_path[:-1].index(curr_path[-1])

                cycle = curr_path[index:-1]
                cycle_key = (cycle[0], cycle[-1])

                if cycle_key not in visited_cycles:
                    visited_cycles.add(cycle_key)
                    yield cycle
                continue

            if curr_path[-1] in visited:
                continue

            visited.add(curr_path[-1])

            for _, neighbour_vertex in adjacency_dict.get(curr_path[-1], []):
                if neighbour_vertex == curr_path[-1]:
                    continue
                queue.append(curr_path + [neighbour_vertex])


@dataclasses.dataclass(slots=True)
class Cycle(Generic[VT, ET]):
    # if we implement flattening we can also remove "Cycle" from the type definition
    sub_graph: "Graph[VT | Cycle[VT, ET], ET]"
    cycle: list[int]


def collapse_cycles(graph: Graph[VT, ET]) -> Graph[Cycle[VT, ET] | VT, ET]:
    # rem
    rtn: Graph[VT | Cycle[VT, ET], ET] = graph.copy()

    while collect_cycles_rtn := list(collect_cycles(rtn)):
        replacements_dict: dict[int, int] = {}
        replacements_dict_reverse: dict[int, list[int]] = {}

        adjacency_dict = rtn.adjacency_dict()
        reverse_adjacency_dict = rtn.reverse().adjacency_dict()

        for original_cycle in collect_cycles_rtn:
            cycle = list(set(replacements_dict.get(x, x) for x in original_cycle))

            vertices_from = list(
                set(
                    y
                    for x in cycle
                    for _, y in reverse_adjacency_dict.get(x, [])
                    # adjacency matrix includes the items in the cycle
                    if y not in cycle
                )
            )
            vertices_into = list(
                set(
                    y
                    for x in cycle
                    for _, y in adjacency_dict.get(x, [])
                    # adjacency matrix includes the items in the cycle
                    if y not in cycle
                )
            )
            # todo if any of the vertices in there are also cycles, un-collapse them?
            cycle_sub_graph = Cycle(
                sub_graph=rtn.map(
                    v=lambda x: x
                    if (x in cycle or x in vertices_from or x in vertices_into)
                    else None,
                    e=lambda e, v1, v2: (e, v1, v2)
                    if (v1 in cycle or v2 in cycle)
                    else None,
                ),
                cycle=cycle,
            )
            rtn = rtn.copy()
            cycle_vertex_id = rtn.vertex_next_id()
            rtn.v.append(cycle_vertex_id)
            rtn.v_labels[cycle_vertex_id] = cycle_sub_graph

            def edge_mapper(e: int, v1: int, v2: int) -> tuple[int, int, int] | None:
                if v1 in vertices_from and v2 in cycle:
                    return e, v1, cycle_vertex_id
                elif v1 in cycle and v2 in vertices_into:
                    return e, cycle_vertex_id, v2
                elif v1 in cycle and v2 in cycle:
                    return None
                else:
                    return e, v1, v2

            rtn = rtn.map(
                v=lambda x: x if x not in cycle else None,
                e=edge_mapper,
            )

            replacement_vertices = []

            for x in original_cycle:
                replacement_vertices.append(x)

            # cleanup for recursive replacements

            # `cycle` and not `original_cycle` because aliases have already been resolved
            for recursive_replacement_vertex in cycle:
                # may be working on stale data
                match cycle_sub_graph.sub_graph.v_labels.get(
                    recursive_replacement_vertex
                ):
                    case Cycle():
                        pass
                    case _:
                        continue

                # that happens is the other loop already did one loop
                if recursive_replacement_vertex not in replacements_dict_reverse:
                    continue
                else:
                    raise AssertionError(
                        "cycles should be resolved in such a way that they are unique and maximal"
                    )

                for x in replacements_dict_reverse[recursive_replacement_vertex]:
                    replacement_vertices.append(x)

                del replacements_dict_reverse[recursive_replacement_vertex]

            for x in replacement_vertices:
                replacements_dict[x] = cycle_vertex_id
            replacements_dict_reverse[cycle_vertex_id] = replacement_vertices

            # make ure that replacements of replacements are also updated

            # todo could use the infromation above to fix adjacency dicts
            adjacency_dict = rtn.adjacency_dict()
            reverse_adjacency_dict = rtn.reverse().adjacency_dict()

    return rtn


def leaves(graph: Graph[VT, ET]) -> Iterator[int]:
    adjacency_dict = graph.adjacency_dict()
    for v in graph.v:
        if not adjacency_dict.get(v, []):
            yield v


def clean_graph(graph: Graph[VT, ET]) -> Graph[VT, ET]:
    # remove self cycles
    rtn = graph.map(e=lambda idx, v1, v2: (idx, v1, v2) if v1 != v2 else None)
    # remove repeating edges

    edge_ids_keep = set(
        idx
        for _, sub_items in itertools.groupby(
            sorted(rtn.e, key=lambda x: x[1:]), key=lambda x: x[1:]
        )
        for (idx, v1, v2), *_ in [sub_items]
    )
    rtn = rtn.map(e=lambda idx, v1, v2: (idx, v1, v2) if idx in edge_ids_keep else None)

    return rtn


def tarjan(graph: Graph[VT, ET]) -> list[list[int]]:
    adjacency_dict = graph.adjacency_dict()

    index_ctr: Iterator[int] = itertools.count()
    stack: list[int] = []
    index_dict: dict[int, int] = {}
    lowlink_dict: dict[int, int] = {}
    on_stack_dict: dict[int, bool] = {}

    rtn: list[list[int]] = []

    # todo rewrite as a continuation

    def strong_connect(v: int) -> None:
        index_dict[v] = next(index_ctr)
        lowlink_dict[v] = index_dict[v]

        stack.append(v)
        on_stack_dict[v] = True

        for _, w in adjacency_dict.get(v, []):
            if index_dict.get(w) is None:
                # successor w has not yet been visited; recurse on it
                strong_connect(w)
                lowlink_dict[v] = min(lowlink_dict[v], lowlink_dict[w])
            elif on_stack_dict[w]:
                # Successor w is in stack S and hence in the current SCC
                # If w is not on stack, then (v, w) is an edge pointing to an SCC already found and must be ignored
                lowlink_dict[v] = min(lowlink_dict[v], index_dict[w])

        if lowlink_dict[v] == index_dict[v]:
            sub_rtn: list[int] = []
            while True:
                w = stack.pop()
                on_stack_dict[w] = False

                sub_rtn.append(w)
                if w == v:
                    break
            rtn.append(sub_rtn)

    for x in graph.v:
        if index_dict.get(x) is None:
            strong_connect(x)

    return rtn
