from contextlib import contextmanager

from race.abstract import Label
from race.generator.remote import RemoteTimeoutError
from race.generator.thread import thread_yield, ThreadGenerator
from race_tests.generator.test_remote import TestRemoteGenerator as _TestRemoteGenerator, _CustomError
from race_tests.generator import test_remote

TEN = 10


def _fun(n):
    for x in range(n):
        thread_yield(x)


def _generator_fun():
    for i in range(TEN):
        thread_yield(Label.from_yield(i))


def _generator_fun_exc():
    for i in range(TEN):
        thread_yield(Label.from_yield(i))

    raise _CustomError


def _generator_fun_deadlock():
    for i in range(TEN):
        thread_yield(Label.from_yield(i))
    raise RemoteTimeoutError


_MAP = {
    test_remote._generator_fun: _generator_fun,
    test_remote._generator_fun_exc: _generator_fun_exc,
    test_remote._generator_fun_deadlock: _generator_fun_deadlock,
}


class TestThreadGenerator(_TestRemoteGenerator):

    @contextmanager
    def _generator(self, fun):
        with ThreadGenerator(_MAP[fun]) as main:
            yield main
