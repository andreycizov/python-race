import inspect
import logging
import multiprocessing
import threading
from typing import Optional, Any, Dict, Tuple

from dataclasses import dataclass, replace

from race.generator.remote import ReentryError

_LOG = logging.getLogger(__name__)


def _main_thread(thread_gen: 'ThreadGenerator') -> None:
    try:
        thread_gen.thread_main()
    except:
        _LOG.exception('_main_thread')


class Packet:
    pass


@dataclass
class Call(Packet):
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]


@dataclass
class Raise(Packet):
    exception: BaseException


@dataclass
class Yield(Packet):
    payload: Any


@dataclass
class Return(Packet):
    payload: Any


class Exit(Packet):
    pass


class Terminate(Packet, BaseException):
    pass


class _SuperGeneratorExit(BaseException):
    pass


class _AssertionError(BaseException):
    pass


_LOCAL = threading.local()
_LOCAL.generator: Optional['ThreadGenerator'] = None


def thread_ensure_local():
    if getattr(_LOCAL, 'generator', None) is None:
        _LOCAL.generator = None


def thread_store(thread_gen: 'ThreadGenerator') -> None:
    thread_ensure_local()

    if _LOCAL.generator is not None:
        raise _AssertionError

    _LOCAL.generator = thread_gen


def thread_clean() -> None:
    thread_ensure_local()

    if _LOCAL.generator is None:
        raise _AssertionError

    _LOCAL.generator = None


def thread_yield(value: Any = None) -> Any:
    thread_ensure_local()

    if _LOCAL.generator is None:
        raise _AssertionError

    return _LOCAL.generator.thread_yield(value=value)


class AnyCallable:
    def __call__(self, *args, **kwargs) -> Any:
        raise NotImplementedError

@dataclass
class ThreadGenerator:
    fun: AnyCallable
    is_child: bool = False
    is_entered: bool = False
    queue_in: Optional[multiprocessing.Queue] = None
    queue_out: Optional[multiprocessing.Queue] = None
    thread: Optional[threading.Thread] = None

    def open(self):
        self.thread_init()

    def close(self):
        self.thread_attempt_destruct()

    def thread_attempt_destruct(self) -> None:
        if self.thread is not None:
            self.thread_destruct()

    def thread_init(self) -> None:
        if self.thread is not None:
            raise AssertionError

        self.queue_in = multiprocessing.Queue()
        self.queue_out = multiprocessing.Queue()
        self.thread = threading.Thread(
            target=_main_thread,
            args=(replace(self),),
            daemon=True,
        )
        self.thread.start()

    @classmethod
    def thread_raise(cls, thread_obj, exception):
        import ctypes

        found = False
        target_tid = None

        for tid, tobj in threading._active.items():
            if tobj is thread_obj:
                found = True
                target_tid = tid
                break

        if not found:
            # note(sleep) thread may be dead by now due to terminate
            return
            # raise ValueError("Invalid thread object")

        ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, ctypes.py_object(exception))
        # ref: http://docs.python.org/c-api/init.html#PyThreadState_SetAsyncExc

        # THIS DOES NOT KILL THEADS WHICH ARE SLEEPING!!!!
        # note(sleep)
        if ret == 0:
            return
            # raise ValueError("Invalid thread ID")
        elif ret > 1:
            # Huh? Why would we notify more than one threads?
            # Because we punch a hole into C level interpreter.
            # So it is better to clean up the mess.
            ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, 0)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def thread_destruct(self) -> None:
        if self.thread is None:
            raise AssertionError
        self.queue_out.put(Terminate())
        self.thread_raise(self.thread, Terminate())
        # note(sleep) can not join on sleeping threads unfortunately
        # self.thread.join()

        self.queue_in = None
        self.queue_out = None

        self.thread = None

    def thread_yield(self, value: Any) -> Any:
        self.queue_in.put(Yield(value))
        packet = self.queue_out.get()
        if isinstance(packet, Yield):
            return packet.payload
        elif isinstance(packet, Raise):
            raise packet.exception from None
        elif isinstance(packet, Exit):
            raise _SuperGeneratorExit
        elif isinstance(packet, Terminate):
            raise packet
        else:
            raise NotImplementedError(repr(packet))

    def thread_main(self):
        if self.is_child:
            raise AssertionError

        self.is_child = True

        thread_store(self)

        try:
            while True:
                packet = self.queue_out.get()

                if isinstance(packet, Terminate):

                    return

                if not isinstance(packet, Call):
                    raise _AssertionError

                try:
                    rtn = self.fun(*packet.args, **packet.kwargs)

                    if inspect.isgenerator(rtn):
                        raise ValueError('the value returned can not be a generator')

                    self.queue_in.put(Return(rtn))
                except Terminate:
                    return
                except _SuperGeneratorExit:
                    self.queue_in.put(Exit())
                except _AssertionError:
                    raise
                except BaseException as exc:
                    self.queue_in.put(Raise(exc))
        except:
            thread_clean()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self.is_entered:
            raise ReentryError
        self.is_entered = True

        self.queue_out.put(Call(args, kwargs))

        try:
            while True:
                packet = self.queue_in.get()

                if isinstance(packet, Yield):
                    try:
                        next_yield_payload = yield packet.payload
                    except GeneratorExit:
                        self.queue_out.put(Exit())
                        packet = self.queue_in.get()
                        if not isinstance(packet, Exit):
                            raise AssertionError(repr(packet))
                        raise GeneratorExit
                    except BaseException as exc:
                        self.queue_out.put(Raise(exc))
                    else:
                        self.queue_out.put(Yield(next_yield_payload))
                elif isinstance(packet, Raise):
                    raise packet.exception from None
                elif isinstance(packet, Return):
                    return packet.payload
                else:
                    raise NotImplementedError(repr(packet))
        finally:
            self.is_entered = False

    def __del__(self):
        self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
