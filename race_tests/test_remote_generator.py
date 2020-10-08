import time
import unittest

from race.abstract import Label
from race.remote_generator import RemoteGenerator, ReentryError

TEN = 10


def _generator_fun():
    for i in range(TEN):
        yield Label.from_yield(i)


class _CustomError(Exception):
    pass


def _generator_fun_exc():
    for i in range(TEN):
        yield Label.from_yield(i)

    raise _CustomError


def _generator_fun_deadlock():
    for i in range(TEN):
        yield Label.from_yield(i)
    time.sleep(9999999)


class TestRemoteGenerator(unittest.TestCase):
    def test_once(self):
        with RemoteGenerator.from_fun(_generator_fun) as main:
            client = main.client()

            labels = [x for x in client()]

        self.assertEqual(
            [Label.from_yield(i) for i in range(TEN)],
            labels,
        )

    def test_twice(self):
        with RemoteGenerator.from_fun(_generator_fun) as main:
            client = main.client()

            labels_1 = [x for x in client()]
            labels_2 = [x for x in client()]

        expected = [Label.from_yield(i) for i in range(TEN)]
        self.assertEqual(
            expected,
            labels_1,
        )
        self.assertEqual(
            expected,
            labels_2,
        )

    def test_half_then_one(self):
        with RemoteGenerator.from_fun(_generator_fun) as main:
            client = main.client()

            labels_1 = []
            #
            for i, x in enumerate(client()):
                if i >= 5:
                    # will raise GeneratorExit and must set
                    # semaphore count to 0
                    break
                labels_1.append(x)
            labels_2 = [x for x in client()]

        expected = [Label.from_yield(i) for i in range(TEN)]
        self.assertEqual(
            expected[:5],
            labels_1,
        )
        self.assertEqual(
            expected,
            labels_2,
        )

    def test_non_reentrant(self):
        with RemoteGenerator.from_fun(_generator_fun) as main:
            client = main.client()

            for _ in client():
                with self.assertRaises(ReentryError):
                    for _ in client():
                        pass

    def test_exception(self):
        with RemoteGenerator.from_fun(_generator_fun_exc) as main:
            client = main.client()

            i = -1
            with self.assertRaises(_CustomError):
                # maybe transfer the traceback as well
                for i, lbl in enumerate(client()):
                    self.assertEqual(
                        Label.from_yield(i),
                        lbl
                    )
            self.assertEqual(
                TEN - 1,
                i,
            )

    def test_deadlock(self):
        with RemoteGenerator.from_fun(_generator_fun_deadlock) as main:
            client = main.client()

            i = -1
            with self.assertRaises(TimeoutError):
                # maybe transfer the traceback as well
                for i, lbl in enumerate(client()):
                    self.assertEqual(
                        Label.from_yield(i),
                        lbl
                    )
            self.assertEqual(
                TEN - 1,
                i,
            )
