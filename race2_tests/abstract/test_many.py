from unittest import TestCase

from race2.abstract import Visitor, Execution, ProcessID


class Test(TestCase):
    def test(self):
        def factory() -> Execution:
            def inner(lock_id: int) -> int:
                yield from range(100)

            return Execution({ProcessID(i): inner(i) for i in range(2)})

        vis = Visitor(factory)
        vis.next()

        self.assertEqual(
            (10404, 20604, 202, 40602),
            (len(vis.visited_vertices), len(vis.visited_edges), vis.instantiation_ctr, vis.paths_found_ctr),
        )

