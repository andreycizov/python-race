from multiprocessing import Manager

from dataclasses import field, dataclass
from unittest import TestCase

from race2.abstract import Visitor, Execution, ProcessID, SpecialState, ProcessGenerator
from race2_tests.abstract.util import graphviz


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

        self.assertEqual(48, len(vis.visited_edges))
        self.assertEqual((12, 90), (vis.instantiation_ctr, vis.paths_found_ctr))
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
                            if x == SpecialState.Exit
                        ]
                    )
                    == 2
                ]
            ),
        )

    def test_3(self):
        vis = self.build_visitor(3)

        self.assertEqual(438, len(vis.visited_edges))
        self.assertEqual((108, 1327), (vis.instantiation_ctr, vis.paths_found_ctr))
        spanning_tree = list(vis.spanning_tree())
        self.assertEqual(94033, len(spanning_tree))
        # show that all final states both have all threads finished
        self.assertEqual(
            0,
            len(
                [
                    process__list
                    for process__list, states__list, next_process_id__list in spanning_tree
                    if len(
                        [
                            x
                            for x in states__list[-1].states.values()
                            if x == SpecialState.Exit
                        ]
                    )
                    == 3
                    and next_process_id__list != []
                ]
            ),
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
        graphviz(vis)

        self.assertEqual(26, len(vis.visited_edges))
        self.assertEqual((7, 37), (vis.instantiation_ctr, vis.paths_found_ctr))
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
                        if x == SpecialState.Exit
                    ]
                )
                >= 1
            ],
        )
