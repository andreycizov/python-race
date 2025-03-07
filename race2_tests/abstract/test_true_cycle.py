from unittest import TestCase

from race2.abstract import Execution, ProcessGenerator, ProcessID, Visitor
from race2.graph.algorithm import clean_graph, collapse_cycles, leaves, Cycle
from race2_tests.abstract.test_cas_spinlock import CAS
from race2.graph.visitor import graph_from_visitor, graph_render_labels


class TestCycle(TestCase):
    def factory(self, number: int) -> Execution:
        locks = CAS()

        def thread_fun(process_id: int) -> ProcessGenerator:
            while True:
                yield "entry"
                LOCK = "a"
                if locks.cas(LOCK, (process_id + 1) % number, None):
                    pass
                    # yield "cancel"

                yield "post_cancel"

                if locks.cas(LOCK, None, process_id):
                    yield "leader_1"
                    while locks.cas(LOCK, process_id, process_id):
                        yield "leader_2"
                    # else:
                    #   yield "leader_2_fail"
                # else:
                #    yield "leader_1_fail"

        rtn = Execution()
        for i in range(number):
            rtn.add_process(ProcessID(i), thread_fun(i))
        return rtn

    def test(self) -> None:
        vis = Visitor(lambda: self.factory(3))
        vis.next()

        self.assertEqual(
            (360, 116, 2013),
            (
                len(vis.visited_edges),
                vis.instantiation_ctr,
                vis.paths_found_ctr,
            ),
        )
        graph = graph_from_visitor(vis)

        # graph_render_labels(graph).graphviz_render(
        #     "/home/andrey/Downloads/true_cycle_0.gv"
        # )

        graph_cycles_collapes = clean_graph(collapse_cycles(graph))
        #
        # graph_render_labels(graph_cycles_collapes).graphviz_render(
        #     "/home/andrey/Downloads/true_cycle.gv"
        # )

        (leaf,) = leaves(graph_cycles_collapes)

        leaf_label = graph_cycles_collapes.v_labels[leaf]
        self.assertEqual(Cycle, leaf_label.__class__)

        # graph_render_labels(leaf_label.sub_graph).graphviz_render(
        #     "/home/andrey/Downloads/true_cycle_2.gv",
        #     vertex_colour_dict={
        #         k: "red" for k in leaf_label.sub_graph.v if k not in leaf_label.cycle
        #     },
        #     edge_colour_dict={
        #         k: "red"
        #         for k, v1, v2 in leaf_label.sub_graph.e
        #         if v1 not in leaf_label.cycle or v2 not in leaf_label.cycle
        #     },
        # )
