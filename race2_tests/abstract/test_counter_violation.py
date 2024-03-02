from unittest import TestCase

from race2.abstract import Visitor, Execution, ProcessID
from race2.util.graphviz import graphviz


class Test(TestCase):
    def test(self):
        def factory() -> Execution:
            glo: dict[str, int] = dict()

            def increase(name: str, by: int = 1) -> int:
                x = glo.get(name, 0)
                yield 1
                glo[name] = x + by
                yield 2

            return Execution({ProcessID(i): increase("a") for i in range(2)})

        vis = Visitor(factory)
        vis.next()

        graphviz(vis)
        self.assertEqual(24, len(vis.visited_edges))
        self.assertEqual((6, 30), (vis.instantiation_ctr, vis.paths_found_ctr))

        self.assertEqual(
            20,
            len(
                [
                    None
                    for _, _, following_nodes in vis.spanning_tree()
                    if following_nodes == []
                ]
            ),
        )
