from unittest import TestCase

from race2.graph.abstract import Graph
from race2.graph.algorithm import collect_cycles


class Test(TestCase):
    def test_a(self):
        self.assertEqual(
            # we do not collect self-cycles anymore
            # [[1, 2], [3]],
            [[1, 2]],
            [
                sorted(x)
                for x in collect_cycles(
                    Graph(
                        [1, 2, 3, 4, 5],
                        [
                            (i, a, b)
                            for i, (a, b) in enumerate([(1, 2), (2, 1), (3, 3), [4, 5]])
                        ],
                    )
                )
            ],
        )

    def test_b(self):
        self.assertEqual(
            [[1, 2, 3]],
            [
                sorted(x)
                for x in collect_cycles(
                    Graph.from_adjacency_list([(1, 2), (2, 1), (2, 3), [3, 2]])
                )
            ],
        )

    def test_c(self):
        self.assertEqual(
            # we do not collect self-cycles anymore
            [[1, 2]],
            [
                sorted(x)
                for x in collect_cycles(
                    Graph.from_adjacency_list([(1, 2), (2, 1), (3, 1)])
                )
            ],
        )
