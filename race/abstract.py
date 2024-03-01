import functools
import inspect
import math
from collections import deque
from typing import (
    List, Tuple, Optional, Callable, Generator, Deque, Dict, Any, Union, Iterator,
)

from dataclasses import dataclass, field, replace

from race.path import Root

RaceGenerator = Generator[None, None, Any]


@dataclass
class Racer:
    fun: Callable

    def __call__(self, *args, **kwargs):
        gen_obj = self.fun(*args, **kwargs)

        while True:
            try:
                yield next(gen_obj)
            except StopIteration as exc:
                return exc.value


def racer(fun) -> Racer:
    return functools.wraps(fun)(Racer(fun))


@dataclass()
class RaceInstance:
    races: List[RaceGenerator]

    def __post_init__(self):
        for x in self.races:
            if not inspect.isgenerator(x):
                raise AssertionError(repr(x))

    def __enter__(self) -> 'RaceInstance':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Instantiator:
    count: int

    def instantiate(self) -> RaceInstance:
        raise NotImplementedError


@dataclass
class CallbackInstantiator(Instantiator):
    count: int
    callback: Callable[[], List[Callable[[], RaceGenerator]]]

    def instantiate(self) -> RaceInstance:
        callbacks = self.callback()

        if not len(callbacks) == self.count:
            raise AssertionError

        return RaceInstance([x() for x in callbacks])


@dataclass(frozen=True)
class Label:
    """is_empty labels are never equal to it's previous labels ?"""

    # todo maybe we should just disable ``None`` labels

    is_empty: bool = True
    is_exit: bool = False
    payload: Any = None

    @classmethod
    def from_yield(cls, value=None) -> 'Label':
        if value is None:
            return cls.from_empty()
        elif isinstance(value, Label):
            return value
        else:
            return Label(is_empty=False, payload=value)

    @classmethod
    def from_empty(cls) -> 'Label':
        return Label()

    @classmethod
    def from_exit(cls) -> 'Label':
        return Label(is_empty=False, is_exit=True)

    def __eq__(self, other: 'Label'):
        if not isinstance(other, Label):
            return False

        if self.is_empty or other.is_empty:
            return False

        if self.is_exit and other.is_exit:
            return True

        if self.payload == other.payload:
            return True

        return False

    def __hash__(self):
        return hash(self.is_empty) ^ hash(self.is_exit) ^ hash(self.payload)

    def __repr__(self):
        body = ''
        if self.is_empty:
            body = 'None'
        elif self.is_exit:
            body = 'Exit'
        else:
            body = repr(self.payload)

        return f'{self.__class__.__name__}({body})'


PathItem = int


@dataclass()
class Path:
    items: List[PathItem] = field(default_factory=list)
    _hash: Optional[int] = None

    def __post_init__(self):
        if not self._hash is None:
            raise AssertionError

        self._hash = self.init_hash(self)

    @classmethod
    def init_hash(cls, self: 'Path') -> int:
        hash_a = hash(sum(x + 234234234 for x in self.items))
        hash_b = 94859430554

        for i, x in enumerate(self.items):
            hash_b ^= hash(i + 2343243) ^ hash(x + 54364757)

        hash_c = hash(len(self.items))
        rtn = hash_a ^ hash_b ^ hash_c

        return rtn

    def __hash__(self):
        return self._hash

    def __iter__(self) -> Iterator[PathItem]:
        return iter(self.items)

    def __add__(self, other):
        if not isinstance(other, Path):
            raise TypeError

        return Path(self.items + other.items)

    def append(self, item: PathItem) -> 'Path':
        return Path(self.items + [item])


Labels = List[Label]


@dataclass
class ExecuteResult:
    result: Union['ExecuteError', List[Any]]
    path: Path
    labels: Labels

    def collect(self):
        if isinstance(self.result, Raised):
            raise self.result.exception from self.result.exception
        elif isinstance(self.result, ExecuteError):
            raise self.result from self.result
        else:
            return self.result


@dataclass
class Race:
    instantiator: Instantiator = Instantiator()

    def __len__(self):
        return self.instantiator.count

    @classmethod
    def execute_cls(cls, path: Path, instantiated: List[RaceGenerator]) -> Tuple[Labels, List[Any]]:
        # todo make this function "generator-like" - i.e. allow to execute while providing path piecewise
        #      (i.e. PathItem)
        running = list(instantiated)
        rtn = [None for _ in running]
        # we can't throw from here anymore if we also need to return the labels
        labels = []

        for p in path:
            # todo context switching
            # todo do not raise, always return - helps with thinking about the data model
            current = running[p]

            if current is None:
                raise TooEarly(
                    labels=labels,
                )
            try:
                next_label_value = next(current)
            except StopIteration as exc:
                rtn[p] = exc.value
                running[p] = None
                next_label = Label.from_exit()
            except BaseException as exc:
                raise Raised(
                    labels=labels,
                    exception=exc,
                ) from None
            else:
                next_label = Label.from_yield(next_label_value)

            labels += [next_label]

        not_exited = [k for k, v in enumerate(running) if v is not None]

        if not_exited:
            raise NotExited(
                labels=labels,
            )

        return labels, rtn

    def execute(self, path: Path) -> ExecuteResult:
        for t in path:
            if t < 0 or len(self) <= t:
                raise ValueError

        with self.instantiator.instantiate() as instantiated:
            try:
                labels, rtn = self.execute_cls(path, instantiated.races)
            except ExecuteError as exc:
                return ExecuteResult(
                    result=exc,
                    path=path,
                    labels=exc.labels,
                )
            else:
                return ExecuteResult(
                    result=rtn,
                    path=path,
                    labels=labels,
                )


@dataclass
class ExecuteError(Exception):
    labels: Optional[Labels] = None
    path: Optional[Path] = None


class IncompleteExecuteError(ExecuteError):
    pass


class TooEarly(IncompleteExecuteError):
    pass


class NotExited(IncompleteExecuteError):
    pass


@dataclass
class _Raised:
    exception: BaseException


@dataclass
class Raised(ExecuteError, _Raised):
    exception: BaseException


def norm_path(path: Path, labels: Labels) -> Path:
    """remove cycles from the path and return un-cycled path"""
    norm = Root.from_path(
        zip(path, labels)
    ).norm

    return Path([x for x, _ in norm])


@dataclass
class Visitor:
    races: Race
    visited: Dict[Path, bool] = field(default_factory=dict)
    queue: Deque[Path] = field(default_factory=deque)
    depth_first: bool = True

    def __post_init__(self):
        self._push_paths(Path())

    @classmethod
    def from_race(cls, races: Race) -> 'Visitor':
        return Visitor(
            races=races,
        )

    def _push_paths(self, path: Path):
        for x in range(len(self.races)):
            subpath = path.append(x)

            if subpath in self.visited:
                continue

            if self.depth_first:
                self.queue.appendleft(subpath)
            else:
                self.queue.append(subpath)

            self.visited[subpath] = True

    def __iter__(self):
        return self

    def __next__(self) -> ExecuteResult:
        while len(self.queue):
            next_path = self.queue.popleft()

            res = self.races.execute(next_path)

            if isinstance(res.result, ExecuteError):
                # todo we should be able to optimise this path by always trying to finish the available path,
                #      i.e. if it's not finished we continue with DPS/BFS until we reach the end of the path,
                #      (prioritising appropriately) until we have reached a terminal state
                #      from the tests in the test suite we see about 80% of incomplete scenarios for even the most
                #      simple issues
                if isinstance(res.result, NotExited):
                    # NotExited means that `len(next_path) == len(res.labels)`
                    self._push_paths(norm_path(next_path, res.labels))
                    pass
                elif isinstance(res.result, TooEarly):
                    # this is an incompatible configuration of the path
                    pass
                elif isinstance(res.result, Raised):
                    pass
                else:
                    raise NotImplementedError(repr(res.result))

            return res

        raise StopIteration


# django connection management
# /home/andrey/venv/3.6.0-a/lib/python3.6/site-packages/django/db/utils.py


def n_combi_bi(a: int, b: int) -> int:
    return int(math.factorial(a + b) / math.factorial(a) / math.factorial(b))


def n_combi(*ns: int) -> int:
    return functools.reduce(n_combi_bi, ns)
