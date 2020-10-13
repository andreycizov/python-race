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

            self.assertEqual(
                21,
                len(filenames),
            )

    def test_exc(self):
        with ThreadGenerator(Trace(_fun_exc)) as main:
            with self.assertRaises(_Error):
                list(main())
