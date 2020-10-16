import itertools
import os
import unittest

from race.generator.thread import ThreadGenerator
from race.generator.trace import Trace
from race_tests.generator.test_remote import TEN


def _fun():
    for i in range(TEN):
        pass


class _Error(Exception):
    pass


def _fun_exc():
    raise _Error


class TestTraceGenerator(unittest.TestCase):
    def test(self):
        with ThreadGenerator(Trace(_fun)) as main:
            filenames = list(main())

            filenames = [(os.path.split(x)[-1], y) for x, y in filenames]
            filenames = sorted(filenames)
            filenames = itertools.groupby(filenames, key=lambda x: x)
            filenames = {k: len(list(vs)) for k, vs in filenames}

            (filename_a, lineno_a), (filename_b, lineno_b) = filenames.keys()

            self.assertEqual(
                filename_a,
                filename_b,
            )

            self.assertEqual(
                lineno_a,
                lineno_b - 1,
            )

            self.assertEqual(
                {
                    # first line is a comparison, it is executed
                    # one more time that the count of a loop because
                    # we need to also execute it for StopIteration
                    (filename_a, lineno_a): TEN + 1,
                    # the inner body is executed the exact amount of times
                    # as requested by the counter
                    (filename_b, lineno_b): TEN,
                },
                filenames,
            )

    def test_exc(self):
        with ThreadGenerator(Trace(_fun_exc)) as main:
            with self.assertRaises(_Error):
                list(main())
