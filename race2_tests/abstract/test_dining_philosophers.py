import itertools
from unittest import TestCase

from race2.abstract import (
    ProcessGenerator,
    Execution,
    ProcessID,
    Visitor,
    ExecutionState,
    SpecialState,
)
from race2.graph.algorithm import leaves, clean_graph, collapse_cycles, collect_cycles_dict, Cycle, paint
from race2.graph.graphviz import graphviz_render
from race2.graph.visitor import graph_from_visitor, graph_render_labels
from race2_tests.abstract.test_cas_spinlock import CAS


class TestDiningPhilosophers(TestCase):
    def factory(self, is_infinite: bool, number: int) -> Execution:
        locks = CAS()

        def thread_fun(process_id: int) -> ProcessGenerator:
            for _ in range(1) if not is_infinite else itertools.count():
                yield "think"
                lock_id_1 = process_id
                while not locks.cas(str(lock_id_1), None, process_id):
                    yield "acq-1-fail"
                yield "acq-1"
                lock_id_2 = (process_id + 1) % number
                while not locks.cas(str(lock_id_2), None, process_id):
                    yield "acq-2-fail"
                yield "acq-2"
                assert locks.cas(str(lock_id_1), process_id, None)
                yield "rel-1"
                assert locks.cas(str(lock_id_2), process_id, None)
                yield "rel-2"

        rtn = Execution()
        for i in range(number):
            rtn.add_process(ProcessID(i), thread_fun(i))
        return rtn

    def test_infinite(self):
        number_of_philisiphers = 3
        vis = Visitor(lambda: self.factory(True, number_of_philisiphers))
        vis.next()

        self.assertEqual(
            (978, 300),
            (
                len(vis.visited_edges),
                vis.instantiation_ctr,
            ),
        )
        # infinite version of dining philosophers will always eventually end up in full deadlock, prove that

        # show that all roads will eventually lead to a deadlock
        graph = graph_from_visitor(vis)
        graph_cycles_collapes = clean_graph(collapse_cycles(graph))

        # Graphviz takes forever to render this so I could never make it work. Maybe addition of subgraphs for cycles
        # would fix it.
        # graph_render_labels(graph_cycles_collapes).graphviz_render("2.sin.gv")

        graph_render_labels(graph_cycles_collapes).graphviz_render(
            "dining-inf-2.sin.gv",
            relpath=__file__,
            # vertex_group_dict=collect_cycles_dict(graph)
        )

        for cycle_idx, cycle in enumerate(
                sorted([vl for vl in graph_cycles_collapes.v_labels.values() if isinstance(vl, Cycle)],
                       key=lambda x: len(x.sub_graph.v))):
            cycle: Cycle

            gv_parms = dict(
                vertex_colour_dict={x: "red" for x in cycle.cycle},
                edge_colour_dict={**{x: "red" for x, a, b in cycle.sub_graph.e if
                                     a in cycle.cycle and b in cycle.cycle},
                                  **{x: "blue" for x, a, b in cycle.sub_graph.e if
                                     a not in cycle.cycle and b in cycle.cycle},
                                  **{x: "green" for x, a, b in cycle.sub_graph.e if
                                     a in cycle.cycle and b not in cycle.cycle}},
            )

            if cycle_idx == 6:
                graph_render_labels(cycle.sub_graph).graphviz_render(
                    f"dining-inf-2.cycle-{cycle_idx}.sin.gv",
                    relpath=__file__,
                    **gv_parms,
                    engine="sfdp",
                    format="svg",
                )
            else:
                graph_render_labels(cycle.sub_graph).graphviz_render(
                    f"dining-inf-2.cycle-{cycle_idx}.sin.gv",
                    relpath=__file__,
                    **gv_parms,
                )

        leaves_vertices = list(leaves(graph_cycles_collapes))
        self.assertEqual(1, len(leaves_vertices))

        (deadlock_vertex,) = leaves_vertices

        # show that the system will always eventually reach the deadlock state
        self.assertEqual(
            ExecutionState({i: "acq-2-fail" for i in range(number_of_philisiphers)}),
            graph_cycles_collapes.v_labels[deadlock_vertex],
        )

    def test_singular(self):
        vis = Visitor(lambda: self.factory(False, 3))
        vis.next()

        self.assertEqual(
            (1110, 272),
            (
                len(vis.visited_edges),
                vis.instantiation_ctr,
            ),
        )
        graph = graph_from_visitor(vis)
        graph_cycles_collapes = clean_graph(collapse_cycles(graph))
        # finite version deadlocks only in some cases but not the others

        # graph_render_labels(graph).graphviz_render("1.sin.gv")
        adjacency_dict = graph_cycles_collapes.adjacency_dict()

        leaves_vertices = list(leaves(graph_cycles_collapes))

        self.assertEqual(2, len(leaves_vertices))

        mapping = {
            graph_cycles_collapes.v_labels[x]: x for x in leaves_vertices
        }

        completed_v_idx = mapping[ExecutionState({i: SpecialState.Terminated for i in range(3)})]
        failed_v_idx = mapping[ExecutionState({i: "acq-2-fail" for i in range(3)})]

        completed_vs = paint(graph_cycles_collapes, completed_v_idx)
        failed_vs = paint(graph_cycles_collapes, failed_v_idx)

        colour_dict = {
            (True, False): "red",
            (False, True): "green",
            (True, True): "yellow",
            (False, False): "black",
        }

        graphviz_render(
            graph_render_labels(graph_cycles_collapes).graphviz(
                vertex_colour_dict={k: colour_dict[(k in failed_vs, k in completed_vs)] for k in
                                    graph_cycles_collapes.v}),
            "dining-sin-2.sin.gv",
            relpath=__file__,

        )
