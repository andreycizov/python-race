import time
from contextlib import contextmanager

from race.abstract import Label
from race.generator.remote import RemoteGenerator
from race.generator.thread import ThreadGenerator, thread_yield
from race_tests.generator import test_remote
from race_tests.generator.test_remote import (
    TestRemoteGenerator as _TestRemoteGenerator, TEN, _CustomError,
)
from race_tests.generator.test_thread import _generator_fun, _generator_fun_exc


def _generator_fun_exc_immediate():
    raise _CustomError


def _generator_fun_deadlock():
    for i in range(TEN):
        thread_yield(Label.from_yield(i))
    time.sleep(9999999)


_MAP = {
    test_remote._generator_fun: _generator_fun,
    test_remote._generator_fun_exc: _generator_fun_exc,
    test_remote._generator_fun_exc_immediate: _generator_fun_exc_immediate,
    test_remote._generator_fun_deadlock: _generator_fun_deadlock,
}


class TestCombinedGenerator(_TestRemoteGenerator):

    @contextmanager
    def _generator(self, fun):
        with ThreadGenerator(_MAP[fun]) as thread, RemoteGenerator(thread) as remote:
            yield remote.client()
