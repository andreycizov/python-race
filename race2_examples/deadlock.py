from dataclasses import dataclass, field

from race2.abstract import (
    ProcessGenerator,
    Execution,
    ProcessID,
    Visitor,
    SpecialState,
    Path,
)
from race2.util.graphviz import graphviz


@dataclass
class DB:
    items: dict[str, int] = field(default_factory=dict)

    def compare_and_swap(
        self, value_key: str, expected_value: int | None, set_value: int | None
    ) -> bool:
        if self.items.get(value_key) == expected_value:
            self.items[value_key] = set_value
            return True
        else:
            return False


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
        return Execution(
            {ProcessID(i): thread(database, i) for i in range(2)},
        )

    vis = Visitor(factory)
    vis.next()

    graphviz(vis, process_id_map={0: "a", 1: "b"}, filename="deadlock")


if __name__ == "__main__":
    main()
