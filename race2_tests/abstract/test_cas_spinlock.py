from multiprocessing import Manager

from dataclasses import field, dataclass
from unittest import TestCase

from race2.abstract import Visitor, Execution, ProcessID, SpecialState, ProcessGenerator, ExecutionState
from race2.graph.algorithm import leaves, paint
from race2.graph.graphviz import graphviz_render
from race2.graph.visitor import graph_from_visitor, graph_render_labels
from race2.util.graphviz import graphviz


@dataclass
class CAS:
    items: dict[str, int] = field(default_factory=lambda: Manager().dict())

    def cas(self, lock_id: str, a: int | None, b: int | None) -> bool:
        if self.items.get(lock_id) == a:
            self.items[lock_id] = b
            return True
        else:
            return False


class TestCASSpinlock(TestCase):
    def thread_fun(self, locks: CAS, lock_id: int) -> ProcessGenerator:
        yield 1

        while not locks.cas("1", None, lock_id):
            yield 2

        yield 3

        while not locks.cas("1", lock_id, None):
            yield 4

        yield 5

    def factory(self, count: int) -> Execution:
        locks: CAS = CAS()
        return Execution(
            {ProcessID(i): self.thread_fun(locks, i) for i in range(count)}
        )

    def build_visitor(self, count: int) -> Visitor:
        vis = Visitor(lambda: self.factory(count))
        vis.next()
        return vis

    def test_2(self):
        vis = self.build_visitor(2)

        graph_render_labels(graph_from_visitor(vis)).graphviz_render(
            "cas_spinlock.2.gv",
            relpath=__file__,
        )

        self.assertEqual(48, len(vis.visited_edges))
        self.assertEqual((12, 12), (vis.instantiation_ctr, vis.paths_found_ctr))
        self.assertEqual(227, len(list(vis.spanning_tree())))
        self.assertEqual(
            58,
            len(
                [
                    process__list
                    for _, states__list, process__list in vis.spanning_tree()
                    if len(
                    [
                        x
                        for x in states__list[-1].states.values()
                        if x == SpecialState.Terminated
                    ]
                )
                       == 2
                ]
            ),
        )

    def test_3(self):
        vis = self.build_visitor(3)

        graph = graph_from_visitor(vis)

        self.assertEqual((438, 108), (len(vis.visited_edges), vis.instantiation_ctr))

        terminal_v, = leaves(graph)

        v_labels_rev = {v: k for k, v in graph.v_labels.items()}

        mid_terminal_v = {
            i: v_labels_rev[ExecutionState({y: SpecialState.Terminated if y != i else 3 for y in range(3)})]
            for i in range(3)
        }

        mid_terminal_paint = {
            i: paint(graph, v)
            for i, v in mid_terminal_v.items()
        }

        paint_terminal = paint(graph, terminal_v)

        colours = {
            (True, False,)
        }

        def colour_fun(v) -> str:
            colour_hex = sum(
                ((v in painted_vs) * 255) * 256 ** i
                for i, painted_vs in mid_terminal_paint.items()
            )
            colour_hex = 0xffffff - colour_hex

            if colour_hex == 0xffffff and v in paint_terminal:
                return "#000000"
            else:
                return f"#{colour_hex:06x}"

        graphviz_render(
            graph_render_labels(graph).graphviz(vertex_colour_dict={v: colour_fun(v) for v in graph.v}),
            "cas_spinlock.3.gv",
            relpath=__file__,

        )


class TestDeadlock(TestCase):
    def thread_fun(self, locks: CAS, lock_id: int) -> ProcessGenerator:
        yield 1

        while not locks.cas("1", None, lock_id):
            yield 2

        yield 3

    def factory(self, count: int) -> Execution:
        locks: CAS = CAS()
        return Execution(
            {ProcessID(i): self.thread_fun(locks, i) for i in range(count)}
        )

    def build_visitor(self, count: int) -> Visitor:
        vis = Visitor(lambda: self.factory(count))
        vis.next()
        return vis

    def test_deadlock(self):
        vis = self.build_visitor(2)
        graph_render_labels(graph_from_visitor(vis)).graphviz_render(
            "deadlock.2.gv",
            relpath=__file__,
        )

        self.assertEqual(26, len(vis.visited_edges))
        self.assertEqual((7, 7), (vis.instantiation_ctr, vis.paths_found_ctr))
        self.assertEqual(43, len(list(vis.spanning_tree())))
        self.assertEqual(
            [
                [0, 0, 0],
                [1, 1, 1],
                [0, 0, 0, 1],
                [0, 0, 1, 0],
                [0, 1, 0, 0],
                [0, 1, 1, 1],
                [1, 0, 0, 0],
                [1, 0, 1, 1],
                [1, 1, 0, 1],
                [1, 1, 1, 0],
                [0, 0, 0, 1, 1],
                [0, 0, 1, 0, 1],
                [0, 0, 1, 1, 0],
                [0, 1, 0, 0, 1],
                [0, 1, 0, 1, 0],
                [0, 1, 1, 0, 1],
                [0, 1, 1, 1, 0],
                [1, 0, 0, 0, 1],
                [1, 0, 0, 1, 0],
                [1, 0, 1, 0, 1],
                [1, 0, 1, 1, 0],
                [1, 1, 0, 0, 1],
                [1, 1, 0, 1, 0],
                [1, 1, 1, 0, 0],
            ],
            [
                process__list
                for process__list, states__list, next_state__list in vis.spanning_tree()
                if len(
                [
                    None
                    for x in states__list[-1].states.values()
                    if x == SpecialState.Terminated
                ]
            )
                   >= 1
            ],
        )
