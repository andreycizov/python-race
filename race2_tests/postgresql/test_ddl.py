import datetime
import select
import traceback
from unittest import TestCase

import psycopg2

from race2.abstract import Execution, ProcessID, Visitor, ExecutionState, SpecialState
from race2.graph.algorithm import clean_graph, collapse_cycles, leaves, path_from_to
from race2.graph.visitor import graph_from_visitor, graph_render_labels

DSN = "dbname=django_uk user=django password=django host=127.0.0.1 port=54320"


class TestDDLDeadlock(TestCase):

    def factory(self, timeout: float = 2) -> Execution:
        def wait(conn: psycopg2.extensions.connection, until_read: bool = False):
            """

            :param conn:
            :param until_read:  I am not certain this is the right way, but if set to True we're simulating a situation where
                                we have sent the command to the server but the server hadn't yet returned the result of running it
                                - this makes it possible to simulate deadlocks with postgresql, as otherwise one of the queries
                                usually times out instead of deadlocking
            :return:
            """
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

        def fun_ddl(conn: psycopg2.extensions.connection) -> Execution:
            curs = conn.cursor()
            # curs.execute("SET idle_in_transaction_session_timeout = '1s'")
            curs.execute(f"SET statement_timeout = '{timeout}s'")
            wait(conn)
            curs.execute("SET deadlock_timeout = '0.01s'")
            wait(conn)
            curs.execute("BEGIN")
            wait(conn)
            #             # curs.fetchall()
            #             # yield "BEGIN"
            curs.execute("""
                         ALTER TABLE
                             application_application
                             ADD COLUMN created_by_id integer NULL CONSTRAINT application_application_created_by_id_6be13b1b_fk_auth_user_id REFERENCES auth_user ( id ) DEFERRABLE INITIALLY DEFERRED;
                         SET CONSTRAINTS application_application_created_by_id_6be13b1b_fk_auth_user_id IMMEDIATE
                         """)
            wait(conn, until_read=True)
            yield "ALTER IN"
            wait(conn)
            yield "ALTER OUT"
            curs.execute("COMMIT")
            wait(conn, until_read=True)
            yield "COMMIT IN"
            wait(conn)
            # yield "COMMIT"

        def fun_select(conn: psycopg2.extensions.connection) -> Execution:

            curs = conn.cursor()
            curs.execute(f"SET statement_timeout = '{timeout}s'")
            wait(conn)
            curs.execute("SET deadlock_timeout = '0.01s'")
            wait(conn)
            curs.execute("BEGIN")
            wait(conn)

            curs.execute("update auth_user set last_login=%s where id=13662296", (datetime.datetime.now(),))
            wait(conn, until_read=True)
            yield "UPDATE IN"
            wait(conn)
            yield "UPDATE OUT"

            # curs.execute("select * from application_application for update")
            curs.execute("select * from application_application")
            wait(conn, until_read=True)
            yield "SELECT IN"
            wait(conn)
            yield "SELECT OUT"

            curs.execute("COMMIT")
            wait(conn, until_read=True)
            yield "COMMIT IN"
            wait(conn)

        def drop_column():
            for x in [0, 1, 2]:
                try:
                    conn = conn_x[x]
                    # wait(conn)
                    conn.close()
                    wait(conn)
                except psycopg2.InterfaceError:
                    pass

            with psycopg2.connect(DSN) as conn:
                with conn.cursor() as curs:
                    curs.execute("ALTER TABLE application_application DROP IF EXISTS created_by_id;")
                    # curs.fetchall()

        def handle_terminate(x: int):
            try:
                conn_x[x].close()
                wait(conn_x[x])
            except psycopg2.InterfaceError:
                pass

        rtn = Execution(handle_terminate=drop_column)
        conn_1 = psycopg2.connect(DSN, async_=1)
        wait(conn_1)
        rtn.add_process(ProcessID(0), fun_ddl(conn_1), handle_terminate=handle_terminate)
        conn_2 = psycopg2.connect(DSN, async_=1)
        wait(conn_2)
        rtn.add_process(ProcessID(1), fun_select(conn_2), handle_terminate=handle_terminate)
        conn_3 = psycopg2.connect(DSN, async_=1)
        wait(conn_3)
        # rtn.add_process(ProcessID(2), fun_select(conn_3), handle_terminate=handle_terminate)
        conn_x = {
            0: conn_1,
            1: conn_2,
            2: conn_3
        }

        return rtn

    def test(self) -> None:
        with psycopg2.connect(DSN) as conn:
            with conn.cursor() as curs:
                curs.execute("ALTER TABLE application_application DROP IF EXISTS created_by_id;")
                # curs.fetchall()

        vis = Visitor(lambda: self.factory())
        vis.next()
        # for i in range(200):
        #     print("a", i)
        #     vis.next_sub([0, 1, 0])
        # for i in range(200):
        #     print("b", i)
        #     vis.next_sub([0, 1, 1])
        # for i in range(100):
        #     vis.next_sub([0, 0, 1, 0])
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

        pid_map = {0: "DDL", 1: "S1", 2: "S2"}
        graph_render_labels(graph_cycles_collapes, process_id_map=pid_map).graphviz_render(
            "ddl.sin.gv",
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

        # show that the system will always eventually reach the deadlock state
        # self.assertEqual(
        #     ExecutionState({i: "acq-2-fail" for i in range(number_of_philisiphers)}),
        #     graph_cycles_collapes.v_labels[deadlock_vertex],
        # )

    def test_deadlock(self) -> None:
        return
        cnt = 0
        for i in range(500):
            with psycopg2.connect(DSN) as conn:
                with conn.cursor() as curs:
                    curs.execute("ALTER TABLE application_application DROP IF EXISTS created_by_id;")
                    # curs.fetchall()

            fac = self.factory(timeout=0.1)
            fac.run([1, 1, 0, 1, 0, 1])

            from psycopg2.errors import DeadlockDetected

            print(fac.rtn.values())

            if any(isinstance(x, DeadlockDetected) for x in fac.rtn.values()):
                cnt += 1

        print(cnt)
        self.assertGreater(cnt, 0)


if __name__ == '__main__':
    TestDDLDeadlock().test()
