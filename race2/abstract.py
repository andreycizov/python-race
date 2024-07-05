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
    Xception = 3

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


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

    handle_terminate: Callable[[], None] = lambda x: None

    def add_process(self, process_id: ProcessID, fun: ProcessGenerator) -> None:
        if process_id in self.curr_processes:
            raise AssertionError("already exists", process_id)

        self.curr_processes[process_id] = fun
        self._curr_state[process_id] = SpecialState.Entry

    # we may be able to rename

    def rename_process(self, process_id: ProcessID, new_process_id: ProcessID) -> None:
        """
        To simulate processes with retries, where the process calls itself multiple times
        When it fails to do something, at the point of the termination of a given process
        we may want to rename the new process to the old one. This way we collapse the
        state tree to a lower set of states. We need to ensure that the new process is indeed
        just like an old one.
        """
        if new_process_id in self.curr_processes:
            raise AssertionError("already exists", new_process_id)

        self.curr_processes[new_process_id] = self.curr_processes.pop(process_id)

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

    def next(self, process_id: ProcessID) -> StateID | SpecialState:
        if process_id not in self.available_processes:
            raise AssertionError("process id not in available processes")

        next_state_id: int | SpecialState
        try:
            next_state_id = next(self.curr_processes[process_id])
        except StopIteration as exc:
            # we intentionally do not handle any exceptions here, exiting is exiting.
            # these should be handled up the call stack
            del self.curr_processes[process_id]
            next_state_id = SpecialState.Terminated

            self.rtn[process_id] = exc.value
        except Exception:
            del self.curr_processes[process_id]
            next_state_id = SpecialState.Xception
            import traceback

            traceback.print_exc()

        self.curr_path.append(process_id)

        self._curr_state[process_id] = next_state_id

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

    def run(self, items: list[ProcessID]) -> list[StateID | SpecialState]:
        rtn: list[StateID | SpecialState] = []
        for x in items:
            rtn.append(self.next(x))
        self.handle_terminate()
        return rtn


@dataclass
class ExecutionState:
    states: dict[ProcessID, StateID | SpecialState] = field(default_factory=dict)

    def __hash__(self):
        return functools.reduce(
            lambda a, b: hash(a) ^ hash(b), sorted(self.states.items()), hash(0)
        )

    @classmethod
    def zero(cls):
        return ExecutionState({})

    def copy(self) -> "ExecutionState":
        return ExecutionState(dict(self.states))

    def __setitem__(self, key: ProcessID, value: StateID | SpecialState) -> None:
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
        ExecutionState,
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
        self.next_sub(Path([]))

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

    def _attempt_push_path(self, path: Path) -> None:
        if self._can_push_path(path):
            self._push_path(path)

    def split_path_visited(self, path: Path) -> tuple[bool, Path, Path]:
        for curr_state in self.root_states:
            for i, next_process_id in enumerate(path):
                # if curr_state != ExecutionState.zero() and all(
                #     v == SpecialState.Exit for v in curr_state.states.values()
                # ):
                #     return False, path[:i], path[i:]

                key = curr_state, next_process_id

                if key in self.visited_edges:
                    curr_state = self.visited_edges[key]
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

    def next_sub(self, seed: Path) -> int:
        self.instantiation_ctr += 1
        current_execution: Execution = self.factory()

        self.root_states.add(current_execution.curr_state)

        paths_found_ctr: int = 0

        while True:
            available_processes = sorted(
                [
                    # using this to make preferred path at the top while the other paths at the bottom
                    (preferred_path is None, x)
                    for x in current_execution.available_processes
                    for path in [Path(current_execution.curr_path + [x])]
                    for preferred_path in [self.decide_next_path(seed, path)]
                    # issue here is that we need to somehow seed this from outside, saying that
                    # we're interested in deeper paths beyond this one
                    if self._can_push_path(preferred_path or path)
                ]
            )

            if not len(available_processes):
                break

            paths_found_ctr += len(available_processes)

            (
                _,
                next_process_id,
            ), *other_next_process_id__list = available_processes

            for _, x in other_next_process_id__list:
                self._push_path(Path(current_execution.curr_path + [x]))

            pre_state = current_execution.curr_state
            current_execution.next(next_process_id)
            self.edge_visit_ctr += 1
            post_state = current_execution.curr_state

            self.visited_edges[(pre_state, next_process_id)] = post_state

        if current_execution.available_processes:
            current_execution.stop()

        return paths_found_ctr

    def next(self) -> None:
        while len(self.queue):
            next_item = self.queue.popleft()

            if not self._can_push_path(next_item):
                continue

            self.paths_found_ctr += self.next_sub(next_item)

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

            yield path, states, next_process_id__list

            for next_process_id in next_process_id__list:
                next_state = self.visited_edges[(states[-1], next_process_id)]

                if next_state in states:
                    continue

                if truly_spanning:
                    if next_state in globally_visited_states:
                        continue
                    globally_visited_states.add(next_state)

                queue.append((path + [next_process_id], states + [next_state]))
