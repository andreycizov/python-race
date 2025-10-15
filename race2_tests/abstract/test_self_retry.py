import functools
import itertools
from unittest import TestCase

from race2.abstract import ProcessGenerator, Execution, ProcessID, Visitor, SpecialState
from race2.graph.visitor import graph_from_visitor, graph_render_labels
from race2.util.graphviz import graphviz
from race2_tests.abstract.test_cas_spinlock import CAS


class TestSelfRetry(TestCase):
    def factory(self) -> Execution:
        locks: CAS = CAS()

        ctr = itertools.count()

        def handle_terminate(id: ProcessID) -> None:
            """
            This function exists to ensure that we do not create unnecessary labels for new
            processes, if we can we immediately rename any additional processes into
            one of the first two processes. This ensures that the state space doesn't grow indefinitely
            """
            if id not in [first_proc_id, second_proc_id]:
                return
            if next_avail := [
                x
                for x in rtn.available_processes
                if x not in [first_proc_id, second_proc_id]
            ]:
                rtn.rename_process(next_avail[0], id)

        def thread_fun(locks: CAS, lock_id: int) -> ProcessGenerator:
            yield "entry"
            if not locks.cas("1", None, lock_id):
                yield "fail"
                # this needs to be at the end of the function, you can think of this as an implementation of
                # tail recursion, i.e. that the termination of one process needs to be in sync with a creation of another
                # if that's not the case we will get a runaway number of processes
                new_id = next(ctr)
                rtn.add_process(
                    new_id,
                    thread_fun(locks, new_id),
                    handle_terminate=handle_terminate,
                )
            else:
                yield "success"
                assert locks.cas(
                    "1",
                    lock_id,
                    None,
                )

        def handle_step(*args, **kwargs):
            """
            This is a function that renames processes in such a way that infinite tail recursion is handled
            without causing infinite growth of state counts
            """
            process_ids = [k for k, v in sorted(rtn.curr_state.states.items(),
                                                key=lambda x: x[1] != SpecialState.Terminated and x[1] != "success")]

            if len(process_ids) != 2:
                return
            terminated_process_id, other_process_id = process_ids

            rtn.rename_process(terminated_process_id, 999)
            rtn.rename_process(other_process_id, 1000)
            rtn.rename_process(999, first_proc_id)
            rtn.rename_process(1000, second_proc_id)

        rtn = Execution(handle_step=handle_step)
        first_proc_id = next(ctr)
        rtn.add_process(
            ProcessID(first_proc_id),
            thread_fun(locks, first_proc_id),
            handle_terminate=handle_terminate,
        )
        second_proc_id = next(ctr)
        rtn.add_process(
            ProcessID(second_proc_id),
            thread_fun(locks, second_proc_id),
            handle_terminate=handle_terminate,
        )
        return rtn

    def build_visitor(self) -> Visitor:
        vis = Visitor(lambda: self.factory())
        vis.next()
        return vis

    def test(self):
        vis = self.build_visitor()

        # self.assertEqual(
        #     (28, 7, 41, 95),
        #     (
        #         len(vis.visited_edges),
        #         vis.instantiation_ctr,
        #         vis.paths_found_ctr,
        #         len(list(vis.spanning_tree())),
        #     ),
        # )
        graph = graph_from_visitor(vis)
        graph_render_labels(graph).graphviz_render(
            "self_retry.gv",
            relpath=__file__,
        )
