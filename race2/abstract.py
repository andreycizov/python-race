import enum
import functools
from collections import deque
from typing import NewType, Generator, Callable, Deque, Any

from dataclasses import dataclass, field

ProcessID = NewType("ProcessID", int)
StateID = NewType("StateID", int)

ProcessGenerator = NewType("ProcessGenerator", Generator[StateID, None, None])


class SpecialState(enum.Enum):
    Entry = 1
    Terminated = 2

    # Xception = 3

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name[:4]}"


UniqueState = NewType("UniqueState", StateID | SpecialState | BaseException)


class Stop(BaseException):
    pass


Path = NewType("Path", list[ProcessID])


@dataclass
class Execution:
    """
    Stores the current list and state of the processes. Each process
    can be `yielded` and gives back it's current unique `StateID`.
    `StateID` is quite abstract, in essence think of it as a uniquely
    identifiable state of some abstract process.
    """

    curr_processes: dict[ProcessID, ProcessGenerator] = field(default_factory=dict)
    curr_path: Path = field(default_factory=list)
    _curr_state: "ExecutionState" = field(default_factory=lambda: ExecutionState())

    rtn: dict[ProcessID, Any] = field(default_factory=dict)

    handle_terminate: Callable[[], None] = lambda: None
    handle_terminate_process: dict[ProcessID, Callable[[ProcessID], None]] = field(
        default_factory=dict
    )
    handle_step: Callable[[], None] = lambda: None

    def add_process(
            self,
            process_id: ProcessID,
            fun: ProcessGenerator,
            handle_terminate: Callable[[ProcessID], None] | None = None,
    ) -> None:
        if process_id in self.curr_processes:
            raise AssertionError("already exists", process_id)

        self.curr_processes[process_id] = fun
        self._curr_state[process_id] = SpecialState.Entry

        self.handle_terminate_process[process_id] = handle_terminate or (lambda x: None)

    # we may be able to rename

    def rename_process(self, process_id: ProcessID, new_process_id: ProcessID) -> None:
        """
        To simulate processes with retries, where the process calls itself multiple times
        When it fails to do something, at the point of the termination of a given process
        we may want to rename the new process to the old one. This way we collapse the
        state tree to a lower set of states. We need to ensure that the new process is indeed
        just like an old one.

        todo replace this with "tailrec_process" and add an addiional check that replace
             can only be called from within a process that is about to terminate
        """
        if new_process_id in self.curr_processes:
            raise AssertionError("already exists", new_process_id)

        if process_id in self.curr_processes:
            self.curr_processes[new_process_id] = self.curr_processes.pop(process_id)
            self.handle_terminate_process[
                new_process_id
            ] = self.handle_terminate_process.pop(process_id)
        self._curr_state[new_process_id] = self._curr_state.states.pop(process_id)

    @property
    def available_processes(self) -> list[ProcessID]:
        return list(self.curr_processes.keys())

    @property
    def curr_state(self) -> "ExecutionState":
        return self._curr_state.copy()

    def from_path(self, path: Path) -> "Execution":
        for x in path:
            self.next(x)
        return self

    def next(self, process_id: ProcessID) -> UniqueState:
        if process_id not in self.available_processes:
            raise AssertionError("process id not in available processes", process_id, self.available_processes,
                                 self.rtn)

        next_state_id: UniqueState
        handle_terminate_process: bool = False

        def remove_process() -> None:
            nonlocal handle_terminate_process
            del self.curr_processes[process_id]
            handle_terminate_process = True

        try:
            next_state_id = next(self.curr_processes[process_id])
        except StopIteration as exc:
            # we intentionally do not handle any exceptions here, exiting is exiting.
            # these should be handled up the call stack
            next_state_id = SpecialState.Terminated

            self.rtn[process_id] = exc.value
            remove_process()
        except Exception as exc:
            next_state_id = exc
            self.rtn[process_id] = exc
            remove_process()

        self.curr_path.append(process_id)

        self._curr_state[process_id] = next_state_id

        self.handle_step()

        if handle_terminate_process:
            if process_id in self.handle_terminate_process:
                handle_terminate_process_fun = self.handle_terminate_process.pop(process_id)
                handle_terminate_process_fun(process_id)

        if not len(self.available_processes):
            self.handle_terminate()

        return next_state_id

    def stop(self) -> None:
        for process_id, gen in self.curr_processes.items():
            try:
                gen.throw(Stop())
            except Stop:
                pass
            else:
                raise AssertionError
        self.curr_processes = {}
        self.handle_terminate()

    def run(self, items: list[ProcessID]) -> list[UniqueState]:
        rtn: list[UniqueState] = []
        try:
            for x in items:
                rtn.append(self.next(x))
        finally:
            self.handle_terminate()
        return rtn


@dataclass
class ExecutionState:
    states: dict[ProcessID, UniqueState] = field(default_factory=dict)

    def __hash__(self):
        def map_hash(v: UniqueState) -> int:
            if isinstance(v, BaseException):
                return hash(v.__class__)
            else:
                return hash(v)

        return functools.reduce(
            lambda a, b: hash(a) ^ hash(b), sorted((k, map_hash(v)) for k, v in self.states.items()), hash(0)
        )

    def __eq__(self, other: "ExecutionState | Any") -> bool:
        if not isinstance(other, ExecutionState):
            return False
        else:
            missing = object()
            for k in set(self.states.keys()) | set(other.states.keys()):
                val_a = self.states.get(k, missing)
                val_b = other.states.get(k, missing)

                if (val_a is missing) ^ (val_b is missing):
                    return False
                elif isinstance(val_a, BaseException):
                    if not isinstance(val_b, BaseException):
                        return False

                    # some exceptions add too much detail to the message and therefore often unique per execution
                    # if type(val_a) != type(val_b) or val_a.args != val_b.args:
                    if type(val_a) != type(val_b):  # or val_a.args != val_b.args:
                        return False
                elif val_a != val_b:
                    return False

            return True

    @classmethod
    def zero(cls):
        return ExecutionState({})

    def copy(self) -> "ExecutionState":
        return ExecutionState(dict(self.states))

    def __setitem__(self, key: ProcessID, value: UniqueState) -> None:
        self.states[key] = value


ExecutionFactory = NewType("ExecutionFactory", Callable[[], Execution])


@dataclass
class Visitor:
    """
    An ExecutionFactory
    """

    factory: ExecutionFactory
    is_depth_first: bool = False

    visited_edges: dict[
        tuple[ExecutionState, ProcessID],
        dict[ExecutionState, int],
    ] = field(default_factory=dict)
    # we define visits as whole paths, but their uniqueness is checked as only the last edge of the path
    # a single edge is defined as: (process_id_from, state_from), (process_id_to)

    # paths to cover
    queue: Deque[Path] = field(default_factory=deque)

    # todo maybe change this to a single state, it doesn't seem to make sense to have more than 1 really
    root_states: set[ExecutionState] = field(default_factory=set)

    paths_found_ctr: int = 0
    instantiation_ctr: int = 0
    edge_visit_ctr: int = 0

    def __post_init__(self):
        pass

    @property
    def visited_vertices(self) -> list[ExecutionState]:
        return list(
            set(x for x, _ in self.visited_edges.keys())
            | set(x for x in self.visited_edges.values())
        )

    def _can_push_path(self, path: Path) -> bool:
        is_potentially_reachable, _, path_unvisited = self.split_path_visited(path)
        return is_potentially_reachable and len(path_unvisited)

    def _push_path(self, path: Path) -> None:
        if self.is_depth_first:
            self.queue.appendleft(path)
        else:
            self.queue.append(path)

    def split_path_visited(self, path: Path) -> tuple[bool, Path, Path]:
        # have we already visited this path at least once?
        # note a single path can lead to different results, but this needs to be handled differently!
        for curr_state in self.root_states:
            for i, next_process_id in enumerate(path):
                # if curr_state != ExecutionState.zero() and all(
                #     v == SpecialState.Exit for v in curr_state.states.values()
                # ):
                #     return False, path[:i], path[i:]

                key = curr_state, next_process_id

                if key in self.visited_edges:
                    # this is a bit of a workaround, but fine otherwise
                    # this will always return the edge as unvisited once we have visited something rare.
                    curr_state = next(iter(self.visited_edges[key].keys()))
                else:
                    return True, path[:i], path[i:]

        return True, path, Path([])

    @classmethod
    def decide_next_path(
            cls, available_path: Path, preferred_path: Path
    ) -> Path | None:
        """
        A pretty complex logic hidden here.

        1. Check that a and b start from the same string. If not return None.
        2. If a is longer than b, return a
        3. If b is longer than a, return b
        :param available_path:
        :param preferred_path:
        :return:
        """
        prefix_length = min([len(available_path), len(preferred_path)])

        if available_path[:prefix_length] != preferred_path[:prefix_length]:
            return None

        return Path(
            available_path[:prefix_length]
            + (
                available_path[prefix_length:]
                if len(available_path) > len(preferred_path)
                else preferred_path[prefix_length:]
            )
        )

    def next_sub(self, seed: Path, should_push_path_fun: Callable[[Path], bool] = lambda x: True) -> list[Path]:
        """
        Visit path using `seed`, then eagerly visit paths, if `should_push_path_fun` returns `True`
        :param seed:
        :param should_push_path_fun:
        :return:
        """
        self.instantiation_ctr += 1
        current_execution: Execution = self.factory()

        self.root_states.add(current_execution.curr_state)

        # how do we flag non-determinism?

        rtn: list[Path] = []

        while True:
            # seed always increases by 1 path length (this is the way we visit all nodes)
            # that means that if we did in fact NOT visit what we wanted before
            available_processes = sorted(
                [
                    # using this to make preferred path at the top while the other paths at the bottom
                    (preferred_path is None, x)
                    for x in current_execution.available_processes
                    for path in [Path(current_execution.curr_path + [x])]
                    # todo we can also change the preferred path function
                    for preferred_path in [self.decide_next_path(seed, path)]
                    if should_push_path_fun(preferred_path or path)
                ]
            )

            if not len(available_processes):
                break

            (
                _,
                next_process_id,
            ) = available_processes[0]

            for _, x in available_processes:
                rtn.append(Path(current_execution.curr_path + [x]))

            pre_state = current_execution.curr_state
            current_execution.next(next_process_id)
            self.edge_visit_ctr += 1
            post_state = current_execution.curr_state

            # there may be multiple visits of the same state twice, and the post_state may be
            # also multiple
            pre_state_key = (pre_state, next_process_id)

            if pre_state_key not in self.visited_edges:
                self.visited_edges[pre_state_key] = dict()

            if post_state not in self.visited_edges[pre_state_key]:
                self.visited_edges[pre_state_key][post_state] = 0

            self.visited_edges[pre_state_key][post_state] += 1

        if current_execution.available_processes:
            current_execution.stop()
        return rtn

    def _next_once(self, path: Path, should_push_path_fun: Callable[[Path], bool]) -> None:
        if path != Path([]) and not should_push_path_fun(path):
            return

        self.paths_found_ctr += 1

        rtn = self.next_sub(path, lambda x: should_push_path_fun(x))
        for new_item in rtn:
            if self._can_push_path(new_item):
                self._push_path(new_item)

    def next(self, max_iter_count: int | None = None, should_push_path_fun: Callable[[Path], bool] = None) -> None:
        if should_push_path_fun is None:
            should_push_path_fun = self._can_push_path

        self._next_once(Path([]), should_push_path_fun)

        iter_ctr = 0
        while len(self.queue) and (max_iter_count is None or iter_ctr < max_iter_count):
            iter_ctr += 1
            next_item = self.queue.popleft()
            self._next_once(next_item, should_push_path_fun)

    def spanning_tree(
            self, truly_spanning: bool = False
    ) -> Generator[tuple[Path, list[ExecutionState], list[ProcessID]], None, None]:
        """
        This builds a full spanning tree, what if we want just a minimal spanning tree.
        Vertices are absolute states, therefore an edge can be traversed only once1
        """
        queue: Deque[tuple[list[ProcessID], list[ExecutionState]]] = deque()
        queue.appendleft(([], list(self.root_states)))

        globally_visited_states: set[ExecutionState] = set()

        while len(queue):
            path, states = queue.popleft()

            next_process_id__list = [
                next_process_id
                for state, next_process_id in self.visited_edges.keys()
                if state == states[-1]
            ]

            if not truly_spanning:
                yield path, states, next_process_id__list

            for next_process_id in next_process_id__list:
                next_state = self.visited_edges[(states[-1], next_process_id)]

                if next_state in states:
                    continue

                if truly_spanning:
                    if next_state in globally_visited_states:
                        yield path, states, next_process_id__list
                        continue
                    globally_visited_states.add(next_state)

                queue.append((path + [next_process_id], states + [next_state]))
