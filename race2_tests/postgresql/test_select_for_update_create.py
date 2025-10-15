from unittest import TestCase

import psycopg2

from race2.abstract import Execution, ProcessID, Visitor, ExecutionState, SpecialState
from race2.graph.algorithm import clean_graph, collapse_cycles, leaves, path_from_to
from race2.graph.visitor import graph_from_visitor, graph_render_labels

DSN = "dbname=django_uk user=django password=django host=127.0.0.1 port=54320"


class Test(TestCase):
    def setUp(self) -> None:
        with psycopg2.connect(DSN) as conn, conn.cursor() as curs:
            curs.execute("BEGIN")

            curs.execute("""
                         CREATE TABLE IF NOT EXISTS race_table_b
                         (
                             id
                             SERIAL
                             PRIMARY
                             KEY
                         );
                         """)
            curs.execute("""


                         CREATE TABLE IF NOT EXISTS race_table_a
                         (
                             id
                             SERIAL
                             PRIMARY
                             KEY,
                             b_id
                             INT
                             REFERENCES
                             race_table_b
                         (
                             id
                         )
                             );
                         """)

            curs.execute("COMMIT")

    def tearDown(self) -> None:
        conn = psycopg2.connect(DSN)
        curs = conn.cursor()
        curs.execute("DROP TABLE  IF EXISTS race_table_a")
        curs.execute("DROP TABLE  IF EXISTS race_table_b")
        curs.close()
        conn.close()

    def factory(self) -> Execution:
        def set_timeouts(curs: psycopg2.extensions.cursor) -> None:
            curs.execute("SET statement_timeout = '0.1s'")
            curs.execute("SET deadlock_timeout = '0.01s'")

        def fun_ins(conn: psycopg2.extensions.connection) -> Execution:
            curs = conn.cursor()
            # curs.execute("SET idle_in_transaction_session_timeout = '1s'")
            set_timeouts(curs)

            yield "B1"
            curs.execute("BEGIN")

            yield "D1"
            curs.execute("INSERT INTO race_table_a (b_id) VALUES (%s)", [b_id])

            yield "C1"
            curs.execute("COMMIT")

            yield "C2"

            # yield "COMMIT"

        def fun_sel(conn: psycopg2.extensions.connection) -> Execution:
            curs = conn.cursor()
            set_timeouts(curs)

            yield "B1"
            curs.execute("BEGIN")

            yield "S1"
            curs.execute("select * from race_table_b where id=%s for update", [b_id])

            yield "C1"
            curs.execute("COMMIT")

            yield "C2"

        def drop_column():
            for x in [0, 1]:
                try:
                    conn = conn_x[x]
                    # 
                    conn.close()

                except psycopg2.InterfaceError:
                    pass

            with  psycopg2.connect(DSN) as conn, conn.cursor() as curs:
                curs.execute("DELETE FROM race_table_a")
                curs.execute("DELETE FROM race_table_b")

        def handle_terminate(x: int):

            try:
                conn_x[x].close()

            except psycopg2.InterfaceError:
                pass

        with psycopg2.connect(DSN) as conn, conn.cursor() as curs:
            curs.execute("INSERT INTO race_table_b DEFAULT VALUES RETURNING id;")
            (b_id,), *_ = curs.fetchall()
            curs.execute("INSERT INTO race_table_a (b_id) VALUES (%s) returning id", [b_id])
            (a_id,), *_ = curs.fetchall()

        rtn = Execution(handle_terminate=drop_column)
        conn_1 = psycopg2.connect(DSN)

        rtn.add_process(ProcessID(0), fun_ins(conn_1), handle_terminate=handle_terminate)
        conn_2 = psycopg2.connect(DSN)

        rtn.add_process(ProcessID(1), fun_sel(conn_2), handle_terminate=handle_terminate)
        # conn_3 = psycopg2.connect(DSN, async_=1)
        # 
        # rtn.add_process(ProcessID(2), fun_select(conn_3), handle_terminate=handle_terminate)
        conn_x = {
            0: conn_1,
            1: conn_2,
            # 2: conn_3
        }

        return rtn

    def test(self) -> None:

        vis = Visitor(lambda: self.factory())
        vis.next()
        #
        # inv = lambda P: [(x + 1) % 2 for x in P]
        # P = [0, 0, 0, 0, 1, 1, 1, 1]
        #
        # for x in range(500):
        #     vis.next_sub(P)
        #
        # for x in range(500):
        #     vis.next_sub(inv(P))
        #
        # P2 = [1, 1, 0, 0, 1]
        # for x in range(100):
        #     vis.next_sub(P2)
        # for x in range(100):
        #     vis.next_sub(inv(P2))
        #
        # self.assertEqual(
        #     (24, 6, 29),
        #     (
        #         len(vis.visited_edges),
        #         vis.instantiation_ctr,
        #         vis.paths_found_ctr,
        #     ),
        # )
        # infinite version of dining philosophers will always eventually end up in full deadlock, prove that

        # show that all roads will eventually lead to a deadlock
        graph = graph_from_visitor(vis)
        graph_cycles_collapes = clean_graph(collapse_cycles(graph))

        # Graphviz takes forever to render this so I could never make it work. Maybe addition of subgraphs for cycles
        # would fix it.
        # graph_render_labels(graph_cycles_collapes).graphviz_render("2.sin.gv")

        pid_map = {0: "fun_del", 1: "fun_sel"}
        graph_render_labels(graph_cycles_collapes, process_id_map=pid_map).graphviz_render(
            "select_for_update_create.gv",
            relpath=__file__,
        )

        leaves_vertices = list(leaves(graph_cycles_collapes))

        self.assertEqual(
            3,
            len(leaves_vertices),
        )


if __name__ == '__main__':
    Test().test()
