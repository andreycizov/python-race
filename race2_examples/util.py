from dataclasses import dataclass, field


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
