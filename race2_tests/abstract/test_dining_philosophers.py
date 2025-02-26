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
from race2.graph.algorithm import leaves, clean_graph, collapse_cycles
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
            (978, 300, 8577),
            (
                len(vis.visited_edges),
                vis.instantiation_ctr,
                vis.paths_found_ctr,
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
            "/home/andrey/Downloads/dining-inf-2.sin.gv"
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
            (1110, 272, 4537),
            (
                len(vis.visited_edges),
                vis.instantiation_ctr,
                vis.paths_found_ctr,
            ),
        )
        graph = graph_from_visitor(vis)
        graph_cycles_collapes = clean_graph(collapse_cycles(graph))
        # finite version deadlocks only in some cases but not the others

        # graph_render_labels(graph).graphviz_render("1.sin.gv")
        graph_render_labels(graph_cycles_collapes).graphviz_render(
            "/home/andrey/Downloads/dining-sin-2.sin.gv"
        )

        leaves_vertices = list(leaves(graph_cycles_collapes))

        # show that the system may both reach the deadlock state or terminated state
        self.assertEqual(
            {
                ExecutionState({i: "acq-2-fail" for i in range(3)}),
                ExecutionState({i: SpecialState.Terminated for i in range(3)}),
            },
            set(graph_cycles_collapes.v_labels[x] for x in leaves_vertices),
        )
