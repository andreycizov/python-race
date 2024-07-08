from unittest import TestCase

from race2.graph.abstract import Graph
from race2.graph.algorithm import collect_cycles, collapse_cycles, Cycle


class Test(TestCase):
    def test_a(self):
        inp = Graph.from_adjacency_list([(1, 2), (2, 1), (2, 3), (3, 3), [4, 5]])
        rtn = collapse_cycles(inp)

        self.assertEqual(
            Graph.from_adjacency_list(
                [
                    (2, 6, 3),
                    (3, 3, 3),
                    (4, 4, 5),
                ],
                v_labels={
                    6: Cycle(
                        Graph.from_adjacency_list(
                            [
                                (1, 2),
                                (2, 1),
                                (2, 3),
                            ]
                        )
                    )
                },
            ),
            rtn,
        )

    def test_b(self):
        self.assertEqual(
            Graph.from_adjacency_list(
                vertices=[5],
                v_labels={
                    5: Cycle(
                        Graph.from_adjacency_list(
                            [
                                (2, 4, 3),
                                (3, 3, 4),
                            ],
                            v_labels={
                                4: Cycle(
                                    Graph.from_adjacency_list(
                                        [
                                            (1, 2),
                                            (2, 1),
                                            (2, 3),
                                            (3, 2),
                                        ]
                                    )
                                )
                            },
                        )
                    )
                },
            ),
            collapse_cycles(
                Graph.from_adjacency_list([(1, 2), (2, 1), (2, 3), [3, 2]])
            ),
        )

    def test_c(self):
        inp = Graph.from_adjacency_list(
            # breaking a cycle will introduce another cycle
            [
                (0, 1),
                (1, 2),
                (2, 0),
                (1, 3),
                (3, 2),
            ]
        )
        rtn = collapse_cycles(inp)

        self.assertEqual(
            Graph.from_adjacency_list(
                vertices=[5],
                v_labels={
                    5: Cycle(
                        Graph.from_adjacency_list(
                            [
                                (3, 4, 3),
                                (4, 3, 4),
                            ],
                            v_labels={
                                4: Cycle(
                                    Graph.from_adjacency_list(
                                        [(0, 1), (1, 2), (2, 0), (1, 3), (3, 2)]
                                    )
                                )
                            },
                        )
                    )
                },
            ),
            rtn,
        )

    def test_d(self):
        inp = Graph.from_adjacency_list(
            # using dining philosophers logic, was just a check for coherency
            [
                (101, 101),
                (101, 201),
                (101, 202),
                (102, 102),
                (102, 201),
                (102, 203),
                (103, 103),
                (103, 202),
                (103, 203),
                #
                (201, 201),
                (201, 201),
                (201, 301),
                (202, 202),
                (202, 202),
                (202, 301),
                (203, 203),
                (203, 203),
                (203, 301),
            ]
        )
        rtn = collapse_cycles(inp)

        self.assertEqual(
            inp,
            rtn,
        )

    def test_edges_outside_cycle_correctly_handled(self):
        inp = Graph.from_adjacency_list([(1, 2), (2, 1), (3, 1)])
        rtn = collapse_cycles(inp)

        self.assertEqual(
            Graph.from_adjacency_list(
                [(2, 3, 4)],
                v_labels={
                    4: Cycle(
                        Graph.from_adjacency_list(
                            [
                                (1, 2),
                                (2, 1),
                                (3, 1),
                            ]
                        )
                    )
                },
            ),
            rtn,
        )

    # todo add test for recursive_replacement_vertex
