from unittest import TestCase

from race2.abstract import Visitor, Execution, ProcessID, ProcessGenerator
from race2.util.graphviz import graphviz

CHECK_PROCESS_ID = 2


class Test(TestCase):
    def test(self):
        def factory() -> Execution:
            glo: dict[str, int] = dict()

            def increase(name: str = "a", by: int = 1) -> ProcessGenerator:
                x = glo.get(name, 0)
                yield 1
                glo[name] = x + by
                yield 2

            def check(name: str = "a") -> ProcessGenerator:
                yield from []
                return glo[name]

            done: int = 0

            def handle_terminate(process_id: ProcessID) -> None:
                nonlocal done
                if process_id in [0, 1]:
                    done += 1
                    if done == 2:
                        exec.add_process(ProcessID(CHECK_PROCESS_ID), check())

            exec = Execution(handle_terminate=handle_terminate)
            exec.add_process(ProcessID(0), increase())
            exec.add_process(ProcessID(1), increase())

            return exec

        vis = Visitor(factory)
        vis.next()

        graphviz(vis, process_id_map={0: "a", 1: "b", 2: "X"})
        self.assertEqual(
            (25, 6, 30),
            (len(vis.visited_edges), vis.instantiation_ctr, vis.paths_found_ctr),
        )

        violations = [
            None
            for path, _, following_nodes in vis.spanning_tree()
            if following_nodes == []
            if factory().from_path(path).rtn[ProcessID(CHECK_PROCESS_ID)]
            != CHECK_PROCESS_ID
        ]
        self.assertEqual(
            12,
            len(violations),
        )
        correct = [
            None
            for path, _, following_nodes in vis.spanning_tree()
            if following_nodes == []
            if factory().from_path(path).rtn[ProcessID(CHECK_PROCESS_ID)]
            == CHECK_PROCESS_ID
        ]
        self.assertEqual(
            8,
            len(correct),
        )
