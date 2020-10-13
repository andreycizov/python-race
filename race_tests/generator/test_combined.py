from contextlib import contextmanager

from race.generator.remote import RemoteGenerator
from race.generator.thread import ThreadGenerator
from race_tests.generator.test_remote import TestRemoteGenerator as _TestRemoteGenerator
from race_tests.generator.test_thread import _MAP


class TestCombinedGenerator(_TestRemoteGenerator):

    @contextmanager
    def _generator(self, fun):
        with ThreadGenerator(_MAP[fun]) as thread, RemoteGenerator(thread) as remote:
            yield remote.client()
