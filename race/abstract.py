import functools
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
                next(gen_obj)
            except StopIteration as exc:
                return exc.value


def racer(fun) -> Racer:
    return functools.wraps(fun)(Racer(fun))


@dataclass()
class RaceInstance:
    races: List[RaceGenerator]

    def __enter__(self) -> List[RaceGenerator]:
        return self.races

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Instantiator:
    def _instantiate(self, races: 'Race') -> List[RaceGenerator]:
        return [x.fun() for x in races.items]

    def instantiate(self, races: 'Race') -> RaceInstance:
        return RaceInstance(self._instantiate(races))

# todo we also need a ContextSwitcher!


@dataclass
class CallbackInstantiator(Instantiator):
    fun: Optional[Callable[[], List[Tuple[Union[Tuple[Any, ...], List[Any]], Dict[str, Any]]]]] = None

    def _instantiate(self, races: 'Race') -> List[RaceGenerator]:
        if self.fun is None:
            args = [([], {}) for _ in range(len(races.items))]
        else:
            args = self.fun()
        return [x.fun(*args, **kwargs) for x, (args, kwargs) in zip(races.items, args)]


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

    def __hash__(self):
        return functools.reduce(lambda a, b: a ^ hash(b), enumerate(self.items), 0)

    def __iter__(self) -> Iterator[PathItem]:
        return iter(self.items)

    def __add__(self, other):
        if not isinstance(other, Path):
            raise TypeError

        return Path(self.items + other.items)


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
    items: List[Racer]
    instantiator: Instantiator = Instantiator()

    def __len__(self):
        return len(self.items)

    def instantiate(self) -> RaceInstance:
        return self.instantiator.instantiate(self)

    @classmethod
    def execute_cls(cls, path: Path, instantiated: List[RaceGenerator]) -> Tuple[Labels, List[Any]]:
        running = list(instantiated)
        rtn = [None for _ in running]
        # we can't throw from here anymore if we also need to return the labels
        labels = []

        for p in path:
            # todo context switching
            current = running[p]

            if current is None:
                raise TooEarly(
                    labels=labels,
                )
            try:
                next_label = Label.from_yield(next(current))
            except StopIteration as exc:
                rtn[p] = exc.value
                running[p] = None
                next_label = Label.from_exit()
            except BaseException as exc:
                raise Raised(
                    labels=labels,
                    exception=exc,
                ) from None

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

        with self.instantiate() as instantiated:
            try:
                labels, rtn = self.execute_cls(path, instantiated)
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

    def __post_init__(self):
        self._push_paths(Path())

    @classmethod
    def from_race(cls, races: Race) -> 'Visitor':
        return Visitor(
            races=races,
        )

    def _push_paths(self, path: Path):
        for x in range(len(self.races)):
            subpath = path + Path([x])

            if subpath in self.visited:
                continue

            self.queue.appendleft(subpath)
            self.visited[subpath] = True

    def __iter__(self):
        return self

    def __next__(self) -> ExecuteResult:
        while len(self.queue):
            next_path = self.queue.popleft()

            res = self.races.execute(next_path)

            if isinstance(res.result, ExecuteError):
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
    return functools.reduce(n_combi_bi, ns, 0)
