from race2.abstract import ProcessGenerator
from race2.multiprocessing.remote import RemoteGenerator
from race2.multiprocessing.thread import ThreadGenerator
from race2.multiprocessing.yield_fun import yield_fun_yield
from race2_tests.abstract.test_cas_spinlock import (
    CAS,
    TestDeadlock as _TestDeadlock,
    TestCASSpinlock as _TestCASSpinlock,
)


class TestCASSpinlock(_TestCASSpinlock):
    def setUp(self):
        self.thread_generator__dict = {
            i: ThreadGenerator(self.thread_sub_fun) for i in range(3)
        }
        self.remote_generator__dict = {
            k: RemoteGenerator(v) for k, v in self.thread_generator__dict.items()
        }

        for x in self.thread_generator__dict.values():
            x.open()

        for x in self.remote_generator__dict.values():
            x.open()

    def thread_sub_fun(self, locks: CAS, lock_id: int) -> ProcessGenerator:
        yield_fun_yield(1)

        while not locks.cas("1", None, lock_id):
            yield_fun_yield(2)

        yield_fun_yield(3)

        while not locks.cas("1", lock_id, None):
            yield_fun_yield(4)

        yield_fun_yield(5)

    def thread_fun(self, locks: CAS, lock_id: int) -> int:
        return self.thread_generator__dict[lock_id](locks, lock_id)

    def tearDown(self):
        for x in self.thread_generator__dict.values():
            x.close()

        for x in self.remote_generator__dict.values():
            x.close()


class TestDeadlock(_TestDeadlock):
    def setUp(self):
        self.thread_generator__dict = {
            i: ThreadGenerator(self.thread_sub_fun) for i in range(3)
        }
        self.remote_generator__dict: dict[int, RemoteGenerator] = {
            k: RemoteGenerator(v) for k, v in self.thread_generator__dict.items()
        }

        for x in self.thread_generator__dict.values():
            x.open()

        for x in self.remote_generator__dict.values():
            x.open()

    def thread_sub_fun(self, locks: CAS, lock_id: int) -> ProcessGenerator:
        yield_fun_yield(1)

        while not locks.cas("1", None, lock_id):
            yield_fun_yield(2)

        yield_fun_yield(3)

    def thread_fun(self, locks: CAS, lock_id: int) -> int:
        return self.remote_generator__dict[lock_id].client()(locks, lock_id)

    def tearDown(self):
        for x in self.thread_generator__dict.values():
            x.close()

        for x in self.remote_generator__dict.values():
            x.close()
