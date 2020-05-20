from typing import Optional, List, Iterable, Generic, TypeVar, Union, Tuple

from dataclasses import field, dataclass

V = TypeVar('V')

Node = Union['Point[V], Cycle[V]']


@dataclass
class Point(Generic[V]):
    value: V

    @property
    def head(self) -> Node:
        return self

    @property
    def point(self) -> 'Point':
        return self

    @property
    def norm(self) -> List[V]:
        return [self.value]

    @property
    def is_point(self) -> bool:
        return True

    def __repr__(self):
        return repr(self.value)


@dataclass
class Cycle(Generic[V]):
    between: List[Node] = field(default_factory=list)

    @property
    def head(self) -> Node:
        return self.between[0]

    @property
    def point(self) -> Point:
        return self.between[0].point

    def __repr__(self):
        parts = [repr(x) for x in self.between]

        if len(parts) > 1:
            parts += ['^' + repr(self.head)]

        parts_repr = ', '.join(x for x in parts)

        if len(parts) > 1:
            return f'[{parts_repr}]'
        else:
            return f'{parts[0]}'

    @property
    def is_point(self) -> bool:
        return len(self.between) == 0

    @classmethod
    def norm_cls(cls, point: Optional[Node], between: List[Node]) -> List[V]:
        rtn = []
        last_point: Optional[V] = point

        def _put(y: V):
            nonlocal last_point
            if last_point is None or y != last_point:
                rtn.append(y)
            last_point = y

        if point is not None:
            for y in point.norm:
                _put(y)

        for x in between:
            for y in x.norm:
                _put(y)

        if point is not None:
            for y in point.norm:
                _put(y)

        return rtn

    @property
    def norm(self) -> List[V]:
        return self.norm_cls(self.head, self.between[1:])


@dataclass
class Root(Generic[V]):
    items: List[Node] = field(default_factory=list)

    def merge_cycle(self, last_matching_index: int):
        curr_cycle = self.items[last_matching_index]

        between = self.items[last_matching_index + 1:]

        if len(between) == 0:
            return

        if between == curr_cycle.between:
            self.items = self.items[:last_matching_index + 1]
        else:
            # two cycles are different but follow each other
            self.items = self.items[:last_matching_index]

            # normalization of patterns is important because we're comparing them directly
            #  - however we could instead make their comparison to be equal for same forms in different normals
            # todo maybe this can be made better
            if len(curr_cycle.between) == 0:
                curr_cycle_between = []
            else:
                curr_cycle_between = [
                    curr_cycle
                ]

            self.items.append(
                Cycle(
                    point=curr_cycle.point,
                    between=curr_cycle_between + between,
                )
            )

    def cycle_create(self, head: Node, index: int) -> Optional[Cycle[V]]:
        if index == len(self.items) - 1:
            return

        begin = self.items[index]

        new_cycle = Cycle(
            between=[head] + self.items[index + 1:],
        )

        if begin.is_point:
            self.items = self.items[:index]
        else:
            self.items = self.items[:index + 1]

        exists_index = self.last_equal_index(item=new_cycle)
        # print('lei', exists_index, new_cycle, )

        if exists_index is not None:

            if exists_index == len(self.items) - 1:
                return

            exists = self.items[exists_index]

            new_cycle = Cycle(
                between=[exists] + self.items[exists_index + 1:]
            )

            self.items = self.items[:exists_index]

        return new_cycle

    def put(self, item: V):
        last_matching_index = self.last_matching_index(Point(item))

        # print('<-', item, last_matching_index, self.items)

        if last_matching_index is not None:
            # self.merge_cycle(last_matching_index)
            new_cycle = None
            while True:
                # print('  ', last_matching_index, new_cycle)
                new_cycle = self.cycle_create(*last_matching_index)

                if new_cycle is None:
                    break

                last_matching_index = self.last_matching_index(new_cycle)

                if last_matching_index is None:
                    self.items.append(new_cycle)
                    break
        else:
            # self.items.append(Cycle(point=item))
            self.items.append(Point(value=item))

        # print('  ', item, last_matching_index, self.items)

    def last_matching_index(self, item: Node) -> Optional[Tuple[Node, int]]:
        for i in range(len(self.items) - 1, -1, -1):
            x = self.items[i]

            while True:
                head = x.head
                if head == item:
                    return head, i

                if isinstance(head, Point):
                    break
                x = head
        return None

    def last_equal_index(self, item: Cycle[V]) -> Optional[int]:
        for i in range(len(self.items) - 1, -1, -1):
            x = self.items[i]
            if x == item:
                return i
        return None

    @property
    def norm(self) -> List[V]:
        return Cycle.norm_cls(None, self.items)

    @classmethod
    def from_path(cls, path: Iterable[V]) -> 'Root[V]':
        rtn = Root()
        for k in path:
            rtn.put(k)

        return rtn
