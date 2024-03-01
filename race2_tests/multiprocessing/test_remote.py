from typing import Generator

from race2.abstract import StateID, ProcessGenerator
from race2.multiprocessing.remote import RemoteGenerator
from race2.multiprocessing.thread import ThreadGenerator
from race2.multiprocessing.yield_fun import yield_fun_yield
from race2_tests.abstract.test_cas_spinlock import CAS, TestDeadlock as _TestDeadlock, TestCASSpinlock as _TestCASSpinlock


class TestCASSpinlock(_TestCASSpinlock):
    def setUp(self):
        self.thread_generator__dict = {
            0: RemoteGenerator(super().thread_fun),
            1: RemoteGenerator(super().thread_fun),
            2: RemoteGenerator(super().thread_fun),
        }

        for x in self.thread_generator__dict.values():
            x.open()

    def thread_fun(self, locks: CAS, lock_id: int) -> ProcessGenerator:
        return self.thread_generator__dict[lock_id].client()(locks, lock_id)

    def tearDown(self):
        for x in self.thread_generator__dict.values():
            x.close()


class TestDeadlock(_TestDeadlock):
    def setUp(self):
        self.thread_generator__dict = {
            0: RemoteGenerator(super().thread_fun),
            1: RemoteGenerator(super().thread_fun),
            2: RemoteGenerator(super().thread_fun),
        }

        for x in self.thread_generator__dict.values():
            x.open()

    def thread_fun(self, locks: CAS, lock_id: int) -> ProcessGenerator:
        return self.thread_generator__dict[lock_id].client()(locks, lock_id)

    def tearDown(self):
        for x in self.thread_generator__dict.values():
            x.close()

