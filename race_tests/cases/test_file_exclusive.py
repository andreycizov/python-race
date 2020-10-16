import functools
import os
import tempfile
import time
import unittest
from collections import defaultdict
from typing import Optional, List

from dataclasses import dataclass, field

from race.abstract import Instantiator, RaceInstance, Visitor, Race, IncompleteExecuteError, n_combi, n_combi_bi
from race.generator.remote import RemoteGenerator, RemoteTimeoutError
from race.generator.thread import AnyCallable, ThreadGenerator
from race.generator.trace import Trace


def write(filename, index):
    while True:
        try:
            with open(filename, 'x') as file_obj:
                file_obj.write(str(index))
        except FileExistsError:
            time.sleep(1)


def fun(filename: str, index: int) -> str:
    write(filename, index)

    with open(filename, 'r') as file_obj:
        return file_obj.read()


@dataclass
class Wrapper:
    fun: AnyCallable
    thread: Optional[ThreadGenerator] = None

    def __call__(self, *args, **kwargs):
        if self.thread is None:
            self.thread = ThreadGenerator(Trace(self.fun))
            self.thread.open()

        return self.thread(*args, **kwargs)

    def __del__(self):
        if self.thread is not None:
            self.thread.close()
            self.thread = None


@dataclass
class FileExclusiveInstantiator(Instantiator):
    count: int
    remote: Optional[List[RemoteGenerator]] = None
    files: List[str] = field(default_factory=list)

    def __enter__(self):
        if self.remote is not None:
            raise AssertionError

        self.remote = [RemoteGenerator(fun=Wrapper(fun)) for _ in range(self.count)]

        for x in self.remote:
            x.__enter__()

        return self

    def instantiate(self) -> RaceInstance:
        if self.remote is None:
            raise AssertionError

        filename: str = tempfile.mktemp()
        self.files.append(filename)
        return RaceInstance([x.client()(filename=filename, index=i) for i, x in enumerate(self.remote)])

    def __exit__(self, exc_type, exc_val, exc_tb):
        for x in self.remote:
            x.__exit__(None, None, None)

        self.remote = None

        for f in self.files:
            try:
                os.unlink(f)
            except FileNotFoundError:
                pass


class TestFileExclusive(unittest.TestCase):
    def test(self):
        self.maxDiff = None
        with FileExclusiveInstantiator(2) as instantiator:
            visitor = Visitor.from_race(Race(instantiator))
            visitor.depth_first = False

            scenarios = 0
            incomplete_scenarios = 0
            violations = []

            label_vals = set()

            returns = defaultdict(int)

            max_len_path = None

            for x in visitor:
                scenarios += 1

                if max_len_path is None or len(max_len_path.items) < len(x.path.items):
                    max_len_path = x.path

                if scenarios % 100 == 0:
                    # print(scenarios, returns, len(max_len_path.items), len(visitor.visited), len(visitor.queue),
                    # max_len_path.items)
                    # print(incomplete_scenarios)
                    #
                    # # print(x.path)
                    # # print(x.labels)
                    # print(len(label_vals), n_combi(len(label_vals), len(label_vals)))
                    pass
                try:
                    for x in x.collect():
                        returns[x] += 1

                    for y in x.labels:
                        label_vals.add(y.payload)
                except RemoteTimeoutError:
                    violations += [x]
                except IncompleteExecuteError:
                    incomplete_scenarios += 1
                    continue

            with self.subTest('scenarios'):
                self.assertEqual(
                    10,
                    scenarios,
                )

            with self.subTest('violations'):
                self.assertEqual(
                    6,
                    len(violations),
                )

            with self.subTest('incomplete_scenarios'):
                self.assertEqual(
                    4,
                    incomplete_scenarios,
                )

            with self.subTest('paths'):
                self.assertEqual(
                    [[1, 1], [0, 0], [1, 0, 0], [1, 0, 1], [0, 1, 0], [0, 1, 1]],
                    [list(x.path) for x in violations],
                )

            with self.subTest('returns'):
                self.assertEqual(
                    {},
                    dict(returns)
                )
