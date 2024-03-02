from race2.abstract import SpecialState
from race2.multiprocessing.remote import RemoteGenerator
from race2.multiprocessing.thread import ThreadGenerator
from race2.multiprocessing.trace import TraceYield
from race2.util.graphviz import graphviz
from race2_tests.multiprocessing.test_combined import (
    CAS,
    TestDeadlock as _TestDeadlock,
    TestCASSpinlock as _TestCASSpinlock,
)


class TestCASSpinlock(_TestCASSpinlock):
    def setUp(self):
        self.thread_generator__dict = {
            i: ThreadGenerator(TraceYield(self.thread_sub_fun)) for i in range(3)
        }
        self.remote_generator__dict = {
            k: RemoteGenerator(v) for k, v in self.thread_generator__dict.items()
        }

        for x in self.thread_generator__dict.values():
            x.open()

        for x in self.remote_generator__dict.values():
            x.open()

    def thread_sub_fun(self, locks: CAS, lock_id: int) -> None:
        while not locks.cas("1", None, lock_id):
            pass

        while not locks.cas("1", lock_id, None):
            pass

    def test_2(self):
        vis = self.build_visitor(2)

        self.assertEqual(
            (48, 15, 105),
            (len(vis.visited_edges), vis.instantiation_ctr, vis.paths_found_ctr),
        )
        self.assertEqual(263, len(list(vis.spanning_tree())))
        self.assertEqual(
            64,
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

        self.assertEqual(
            (438, 142, 1623),
            (len(vis.visited_edges), vis.instantiation_ctr, vis.paths_found_ctr),
        )

        self.assertEqual(
            0,
            len(
                [
                    process__list
                    for process__list, states__list, next_process_id__list in vis.spanning_tree()
                    if len(
                        [
                            x
                            for x in states__list[-1].states.values()
                            if x == SpecialState.Terminated
                        ]
                    )
                    == 3
                    and next_process_id__list != []
                ]
            ),
        )


class TestDeadlock(_TestDeadlock):
    def setUp(self):
        self.thread_generator__dict = {
            i: ThreadGenerator(TraceYield(self.thread_sub_fun)) for i in range(3)
        }
        self.remote_generator__dict = {
            k: RemoteGenerator(v) for k, v in self.thread_generator__dict.items()
        }

        for x in self.thread_generator__dict.values():
            x.open()

        for x in self.remote_generator__dict.values():
            x.open()

    def thread_sub_fun(self, locks: CAS, lock_id: int) -> None:
        while not locks.cas("1", None, lock_id):
            pass

    def test_deadlock(self):
        vis = self.build_visitor(2)
        graphviz(vis)

        self.assertEqual(
            (26, 8, 41),
            (len(vis.visited_edges), vis.instantiation_ctr, vis.paths_found_ctr),
        )
        self.assertEqual(49, len(list(vis.spanning_tree())))
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
                [0, 0, 1, 1, 0, 1],
                [0, 1, 0, 1, 0, 1],
                [0, 1, 1, 0, 1, 0],
                [1, 0, 0, 1, 0, 1],
                [1, 0, 1, 0, 1, 0],
                [1, 1, 0, 0, 1, 0],
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
