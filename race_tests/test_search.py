import functools
import unittest
from collections import defaultdict
from typing import Dict, Optional

from dataclasses import dataclass, field

from race.abstract import (
    Visitor, racer, Race, CallbackInstantiator,
    IncompleteExecuteError,
)


@dataclass
class Globals:
    items: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def get(self, name: str) -> int:
        return self.items[name]

    def set(self, name: str, val: int):
        self.items[name] = val


@dataclass
class CAS:
    items: Dict[str, int] = field(default_factory=dict)

    def cas(self, lock_id: str, a: Optional[int], b: Optional[int]) -> bool:
        if self.items.get(lock_id) == a:
            self.items[lock_id] = b
            return True
        else:
            return False


@dataclass
class Locks:
    items: Dict[int, int] = field(default_factory=dict)

    def lock(self, lock_id: int, locking_id: int) -> 'Lock':
        return Lock(self, lock_id, locking_id)


@dataclass
class Lock:
    locks: Locks
    lock_id: int
    locking_id: int
    is_reentrant = False

    def __enter__(self) -> 'Lock':
        self.is_reentrant = False
        if self.locks.items.get(self.lock_id) is None:
            self.locks.items[self.lock_id] = self.locking_id
        elif self.locks.items.get(self.lock_id) == self.locking_id:
            self.is_reentrant = True
        else:
            raise Deadlock()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.is_reentrant:
            del self.locks.items[self.lock_id]


class Deadlock(Exception):
    pass


class TestExecutions(unittest.TestCase):
    def test_counter_violation(self):
        @racer
        def increase(vars: Globals, name: str, by: int = 1):
            x = vars.get(name)
            yield 'A'
            vars.set(name, x + by)
            yield 'B'
            return vars.get(name)

        def instantiate():
            globs = Globals()

            return [
                functools.partial(
                    increase,
                    vars=globs,
                    name='a',
                )
                for i in range(2)
            ]

        visitor = Visitor.from_race(Race(CallbackInstantiator(2, instantiate)))

        scenarios = 0
        incomplete_scenarios = 0
        violations = []
        for x in visitor:
            try:
                if max(x.collect()) != 2:
                    violations.append(x)
            except IncompleteExecuteError:
                incomplete_scenarios += 1
                continue

            scenarios += 1

        self.assertEqual(
            20,
            scenarios,
        )

        self.assertEqual(
            78,
            incomplete_scenarios,
        )

        self.assertEqual(
            [
                [1, 0, 1, 1, 0, 0],
                [1, 0, 1, 0, 1, 0],
                [1, 0, 1, 0, 0, 1],
                [1, 0, 0, 1, 1, 0],
                [1, 0, 0, 1, 0, 1],
                [1, 0, 0, 0, 1, 1],
                [0, 1, 1, 1, 0, 0],
                [0, 1, 1, 0, 1, 0],
                [0, 1, 1, 0, 0, 1],
                [0, 1, 0, 1, 1, 0],
                [0, 1, 0, 1, 0, 1],
                [0, 1, 0, 0, 1, 1]
            ],
            [list(x.path) for x in violations],
        )

    def test_cas_potentially_infinite(self):
        @racer
        def cas(globs: Globals, locks: CAS, lock_id: str, locking_id: int):
            yield 'a'

            # this technically may expand into executions of a single thread for forever (before the second one)
            # thus should imply infinite cycles in the analyser
            while not locks.cas(lock_id, None, locking_id):
                yield 'b1'
                yield 'b2'

            yield 'c'

            value = globs.get(lock_id)

            yield 'c1'

            globs.set(lock_id, value + 1)

            yield 'c2'

            while not locks.cas(lock_id, locking_id, None):
                yield 'd'

            yield 'e'

            return globs.get(lock_id)

        def instantiate():
            locks = CAS()
            globs = Globals()

            return [
                functools.partial(
                    cas,
                    globs=globs,
                    locks=locks,
                    lock_id='a',
                    locking_id=i,
                )
                for i in range(2)
            ]

        visitor = Visitor.from_race(Race(CallbackInstantiator(2, instantiate)))

        finishes = []
        incorrect = []

        scenarios = 0
        incomplete_scenarios = 0

        for x in visitor:

            try:
                res = x.collect()
            except IncompleteExecuteError as exc:
                incomplete_scenarios += 1
                continue
            scenarios += 1

            finishes.append(res)

            if max(res) != 2:
                incorrect.append(res)

        with self.subTest('visited'):
            self.assertEqual(
                48098,
                len(visitor.visited),
            )

        self.assertEqual(
            374,
            len(finishes),
        )

        self.assertEqual(
            0,
            len(incorrect),
        )

        self.assertEqual(
            374,
            scenarios,
        )

        self.assertEqual(
            2480,
            incomplete_scenarios,
        )

    def test_deadlock(self):
        @racer
        def cas(locks: Locks, lock_id, locking_id):
            yield 'a'

            with locks.lock(lock_id, locking_id):
                yield 'b'

            yield 'c'

        def instantiate():
            locks = Locks()

            return [
                functools.partial(
                    cas,
                    locks=locks,
                    lock_id='a',
                    locking_id=i,
                )
                for i in range(2)
            ]

        visitor = Visitor.from_race(Race(CallbackInstantiator(2, instantiate)))

        deadlocks = []
        non_deadlocks = []

        scenarios = 0
        incomplete_scenarios = 0

        for x in visitor:
            try:
                x.collect()
                non_deadlocks.append(x)
            except Deadlock:
                deadlocks.append(x)
            except IncompleteExecuteError:
                incomplete_scenarios += 1
                continue

            scenarios += 1

        # it's interesting that all of these are quite short?

        self.assertEqual(
            40,
            scenarios,
        )

        self.assertEqual(
            166,
            incomplete_scenarios,
        )

        self.assertEqual(
            [
                [1, 1, 0, 0],
                [1, 0, 1, 0],
                [1, 0, 0, 1],
                [0, 1, 1, 0],
                [0, 1, 0, 1],
                [0, 0, 1, 1]
            ],
            [list(x.path) for x in deadlocks],
        )

        self.assertEqual(
            [
                [1, 1, 1, 1, 0, 0, 0, 0],
                [1, 1, 1, 0, 1, 0, 0, 0],
                [1, 1, 1, 0, 0, 1, 0, 0],
                [1, 1, 1, 0, 0, 0, 1, 0],
                [1, 1, 1, 0, 0, 0, 0, 1],
                [1, 1, 0, 1, 1, 0, 0, 0],
                [1, 1, 0, 1, 0, 1, 0, 0],
                [1, 1, 0, 1, 0, 0, 1, 0],
                [1, 1, 0, 1, 0, 0, 0, 1],
                [1, 0, 1, 1, 1, 0, 0, 0],
                [1, 0, 1, 1, 0, 1, 0, 0],
                [1, 0, 1, 1, 0, 0, 1, 0],
                [1, 0, 1, 1, 0, 0, 0, 1],
                [1, 0, 0, 0, 1, 1, 1, 0],
                [1, 0, 0, 0, 1, 1, 0, 1],
                [1, 0, 0, 0, 1, 0, 1, 1],
                [1, 0, 0, 0, 0, 1, 1, 1],
                [0, 1, 1, 1, 1, 0, 0, 0],
                [0, 1, 1, 1, 0, 1, 0, 0],
                [0, 1, 1, 1, 0, 0, 1, 0],
                [0, 1, 1, 1, 0, 0, 0, 1],
                [0, 1, 0, 0, 1, 1, 1, 0],
                [0, 1, 0, 0, 1, 1, 0, 1],
                [0, 1, 0, 0, 1, 0, 1, 1],
                [0, 1, 0, 0, 0, 1, 1, 1],
                [0, 0, 1, 0, 1, 1, 1, 0],
                [0, 0, 1, 0, 1, 1, 0, 1],
                [0, 0, 1, 0, 1, 0, 1, 1],
                [0, 0, 1, 0, 0, 1, 1, 1],
                [0, 0, 0, 1, 1, 1, 1, 0],
                [0, 0, 0, 1, 1, 1, 0, 1],
                [0, 0, 0, 1, 1, 0, 1, 1],
                [0, 0, 0, 1, 0, 1, 1, 1],
                [0, 0, 0, 0, 1, 1, 1, 1]
            ],
            [list(x.path) for x in non_deadlocks],
        )
