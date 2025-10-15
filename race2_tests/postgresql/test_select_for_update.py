import select
import traceback
from unittest import TestCase

import psycopg2

from race2.abstract import Execution, ProcessID, Visitor, ExecutionState, SpecialState
from race2.graph.algorithm import clean_graph, collapse_cycles, leaves, path_from_to
from race2.graph.visitor import graph_from_visitor, graph_render_labels

DSN = "dbname=django_uk user=django password=django host=127.0.0.1 port=54320"


class TestDDLDeadlock(TestCase):
    def setUp(self) -> None:
        with psycopg2.connect(DSN) as conn, conn.cursor() as curs:
            curs.execute("BEGIN")

            curs.execute("DROP TABLE  IF EXISTS race_table_a")

            curs.execute("""
                         CREATE TABLE IF NOT EXISTS race_table_a
                         (
                             id
                             SERIAL
                             PRIMARY
                             KEY
                         );
                         """)
            curs.execute("""COMMIT""");




    def tearDown(self):
        with psycopg2.connect(DSN) as conn, conn.cursor() as curs:
            curs.execute("BEGIN")

            curs.execute("DROP TABLE  IF EXISTS race_table_a")
            curs.execute("""COMMIT""");


    def factory(self) -> Execution:
        def wait(conn: psycopg2.extensions.connection, until_read: bool = False):
            while True:
                state = conn.poll()
                if state == psycopg2.extensions.POLL_OK:
                    break
                elif state == psycopg2.extensions.POLL_WRITE:
                    select.select([], [conn.fileno()], [])
                elif state == psycopg2.extensions.POLL_READ:
                    if until_read:
                        assert conn.isexecuting()
                        break
                    else:
                        select.select([conn.fileno()], [], [])
                else:
                    raise psycopg2.OperationalError("poll() returned %s" % state)

        def set_timeouts(conn: psycopg2.extensions.connection, curs: psycopg2.extensions.cursor) -> None:
            curs.execute("SET statement_timeout = '0.1s'")
            wait(conn)
            curs.execute("SET deadlock_timeout = '0.01s'")
            wait(conn)

        def fun_ba(conn: psycopg2.extensions.connection) -> Execution:
            curs = conn.cursor()
            set_timeouts(conn, curs)
            yield "B1"
            curs.execute("BEGIN")
            wait(conn)
            yield "B2"
            curs.execute("select * from race_table_a where id=%s for update", [a_id])
            wait(conn, until_read=True)
            yield "S1"
            wait(conn)
            curs.execute("select * from race_table_a where id=%s for update", [b_id])
            wait(conn, until_read=True)
            yield "S2"
            wait(conn)
            yield "C1"
            curs.execute("COMMIT")
            wait(conn, until_read=True)
            yield "C2"
            wait(conn)
            # yield "COMMIT"

        def fun_ab(conn: psycopg2.extensions.connection) -> Execution:
            curs = conn.cursor()
            set_timeouts(conn, curs)
            yield "B1"
            curs.execute("BEGIN")
            wait(conn)
            yield "B2"
            curs.execute("select * from race_table_a where id=%s for update", [b_id])
            wait(conn, until_read=True)
            yield "S1"
            wait(conn)
            curs.execute("select * from race_table_a where id=%s for update", [a_id])
            wait(conn, until_read=True)
            yield "S2"
            wait(conn)
            yield "C1"
            curs.execute("COMMIT")
            wait(conn, until_read=True)
            yield "C2"
            wait(conn)

        def drop_column():
            for x in [0, 1]:
                try:
                    conn = conn_x[x]
                    # wait(conn)
                    conn.close()
                    wait(conn)
                except psycopg2.InterfaceError:
                    pass

            with psycopg2.connect(DSN) as conn, conn.cursor() as curs:
                curs.execute("delete from race_table_a;")

        def handle_terminate(x: int):
            try:
                conn_x[x].close()
                wait(conn_x[x])
            except psycopg2.InterfaceError:
                pass


        with psycopg2.connect(DSN) as conn, conn.cursor() as curs:
            curs.execute("INSERT INTO race_table_a DEFAULT VALUES RETURNING id;")
            (a_id,), *_ = curs.fetchall()
            curs.execute("INSERT INTO race_table_a DEFAULT VALUES RETURNING id;")
            (b_id,), *_ = curs.fetchall()

        rtn = Execution(handle_terminate=drop_column)
        conn_1 = psycopg2.connect(DSN, async_=1)
        wait(conn_1)
        rtn.add_process(ProcessID(0), fun_ba(conn_1), handle_terminate=handle_terminate)
        conn_2 = psycopg2.connect(DSN, async_=1)
        wait(conn_2)
        rtn.add_process(ProcessID(1), fun_ab(conn_2), handle_terminate=handle_terminate)
        # conn_3 = psycopg2.connect(DSN, async_=1)
        # wait(conn_3)
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

        inv = lambda P: [(x + 1) % 2 for x in P]
        P = [0, 0, 0, 0, 1, 1, 1, 1]

        for x in range(500):
            vis.next_sub(P)

        for x in range(500):
            vis.next_sub(inv(P))
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

        pid_map = {0: "ba", 1: "ab"}
        graph_render_labels(graph_cycles_collapes, process_id_map=pid_map).graphviz_render(
            "select_for_update.sin.gv",
            relpath=__file__
        )

        leaves_vertices = list(leaves(graph_cycles_collapes))
        # self.assertEqual(5, len(leaves_vertices))

        state_zero, = [k for k, v in graph_cycles_collapes.v_labels.items() if
                       v in [ExecutionState({0: SpecialState.Entry, 1: SpecialState.Entry}),
                             ExecutionState({0: SpecialState.Entry, 1: SpecialState.Entry, 2: SpecialState.Entry})]]
        for leave in leaves_vertices:
            path = path_from_to(graph_cycles_collapes, state_zero, leave)
            path_mapped = [graph_cycles_collapes.e_labels[x] for x in path]

            print(path_mapped)
        for leave in leaves_vertices:
            path = path_from_to(graph_cycles_collapes, state_zero, leave)
            path_mapped = [graph_cycles_collapes.e_labels[x] for x in path]

            for x in range(10):
                try:
                    fac = self.factory()
                    fac.run(path_mapped)
                    print({pid_map[k]: v for k, v in graph_cycles_collapes.v_labels[leave].states.items()}, path_mapped,
                          {pid_map[k]: v for k, v in fac.rtn.items()})
                except AssertionError:
                    pass
                else:
                    break
            else:
                print(path_mapped, "failed")


if __name__ == '__main__':
    TestDDLDeadlock().test()
