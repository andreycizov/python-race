from race2.abstract import (
    ProcessGenerator,
    Execution,
    ProcessID,
    Visitor,
)
from race2.util.graphviz import graphviz
from race2_examples.util import DB


def main():
    MAX_RETRY_COUNT = 3

    def factory() -> Execution:
        database: DB = DB()

        thread_ctr: int = 0

        def thread(
            database: DB,
            thread_id: int,
            retry_ctr: int = 1,
            max_retry_count: int = MAX_RETRY_COUNT,
        ) -> ProcessGenerator:
            nonlocal thread_ctr

            if database.compare_and_swap(
                value_key="1", expected_value=None, set_value=thread_id
            ):
                yield 1
                database.compare_and_swap(
                    value_key="1", expected_value=thread_id, set_value=None
                )
            elif retry_ctr > max_retry_count:
                pass
            else:
                yield 2
                exec.add_process(
                    ProcessID(thread_ctr),
                    thread(database, thread_ctr, retry_ctr=retry_ctr + 1),
                )

                thread_ctr += 1

        exec = Execution()
        for i in range(2):
            exec.add_process(ProcessID(i), thread(database, i))
            thread_ctr = i + 1
        return exec

    vis = Visitor(factory)
    vis.next()

    # note there's no r3 process, meaning there can never be 3 retries
    graphviz(
        vis,
        process_id_map={
            0: "a",
            1: "b",
            **{k: f"r{k - 2}" for k in range(2, MAX_RETRY_COUNT + 2)},
        },
        filename="retry",
    )


if __name__ == "__main__":
    main()
