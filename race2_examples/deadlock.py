from race2.abstract import (
    ProcessGenerator,
    Execution,
    ProcessID,
    Visitor,
)
from race2.util.graphviz import graphviz
from race2_examples.util import DB


def main():
    def thread(database: DB, thread_id: int) -> ProcessGenerator:
        yield 1

        while not database.compare_and_swap(
            value_key="1", expected_value=None, set_value=thread_id
        ):
            yield 2

        yield 3

    def factory() -> Execution:
        database: DB = DB()
        exec = Execution()
        for i in range(2):
            exec.add_process(ProcessID(i), thread(database, i))
        return exec

    vis = Visitor(factory)
    vis.next()

    graphviz(vis, process_id_map={0: "a", 1: "b"}, filename="deadlock")


if __name__ == "__main__":
    main()
