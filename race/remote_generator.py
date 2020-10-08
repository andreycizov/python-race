import logging
import multiprocessing
from queue import Empty
from subprocess import TimeoutExpired
from typing import Optional, Any, Iterable, Dict, Tuple

from dataclasses import dataclass

from race.abstract import Label

_LOG = logging.getLogger(__name__)


class ChildEvent:
    pass


class Push(ChildEvent):
    pass


@dataclass()
class Reset(ChildEvent):
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]


class Terminate(ChildEvent):
    pass


class ParentEvent:
    pass


class Stop(ParentEvent):
    pass


@dataclass
class Next(ParentEvent):
    label: Label


@dataclass
class Except(ParentEvent):
    exception: Exception


@dataclass
class _Yield(Exception):
    value: Label


@dataclass
class _Raise(Exception):
    exception: Exception


class _Return(Exception):
    pass


class _Exit(Exception):
    pass


FunReturn = Iterable[Label]


class Fun:
    def __call__(self, *args, **kwargs) -> FunReturn:
        raise NotImplementedError


def _main_subprocess(remote_generator: 'RemoteGenerator'):
    try:
        remote_generator.run()
    except:
        _LOG.exception('_main_subprocess raised')


@dataclass
class RemoteGenerator:
    fun: Fun
    in_queue: Optional[multiprocessing.Queue] = None
    out_queue: Optional[multiprocessing.Queue] = None
    process: Optional[multiprocessing.Process] = None

    iter_obj: Optional[Iterable[Label]] = None

    join_timeout: float = 10.
    read_timeout: Optional[float] = 1.

    @classmethod
    def from_fun(cls, fun: Fun) -> 'RemoteGenerator':
        rtn = RemoteGenerator(
            fun=fun,
        )

        rtn._process_ensure_running()

        return rtn

    def _process_ensure_running(self):
        if self.process is None:
            self._process_start()

    def _process_ensure_stopped(self):
        if self.process is not None:
            self._process_terminate()

    def _process_start(self):
        if self.process is not None:
            raise AssertionError

        self.in_queue = multiprocessing.Queue(maxsize=1)
        self.out_queue = multiprocessing.Queue(maxsize=1)

        self.process = multiprocessing.Process(
            target=_main_subprocess,
            args=(self,),
            name='race.mp',
            daemon=True,
        )
        self.process.start()

    def _process_terminate(self):
        if self.process is None:
            raise AssertionError

        self.in_queue.put(Terminate())
        self.in_queue = None
        self.out_queue = None
        self.process.terminate()
        self.process.join(timeout=self.join_timeout)
        self.process = None

    def __enter__(self) -> 'RemoteGenerator':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._process_ensure_stopped()

    def client(self) -> 'RemoteGeneratorClient':
        return RemoteGeneratorClient(
            instance=self,
        )

    def _dispatch(self, next_msg: Any):
        if not isinstance(next_msg, ChildEvent):
            raise AssertionError(repr(next_msg))

        if isinstance(next_msg, Push):
            self._dispatch_push(next_msg)
        elif isinstance(next_msg, Reset):
            self._dispatch_reset(next_msg)
        elif isinstance(next_msg, Terminate):
            self._dispatch_terminate(next_msg)
        else:
            raise AssertionError(repr(next_msg))

    def _dispatch_push(self, msg: Push):
        if self.iter_obj is None:
            raise AssertionError

        try:
            next_item = Label.from_yield(next(self.iter_obj))
        except StopIteration:
            self.out_queue.put(Stop())
        except Exception as exc:
            self.out_queue.put(Except(exc))
        else:
            self.out_queue.put(Next(next_item))

    def _dispatch_reset(self, msg: Reset):
        self.iter_obj = self.fun(*msg.args, **msg.kwargs)

    def _dispatch_terminate(self, msg: Terminate):
        raise _Exit()

    def run(self):
        try:
            while True:
                next_msg = self.in_queue.get()

                self._dispatch(next_msg)
        except _Exit:
            pass
        except:
            _LOG.exception('main_child')
        finally:
            _LOG.info('terminating')


class ReentryError(Exception):
    pass


@dataclass
class RemoteGeneratorClient:
    instance: RemoteGenerator
    semaphore: int = 0

    def _dispatch(self, next_item: Any):
        if isinstance(next_item, Stop):
            raise _Return()
        elif isinstance(next_item, Next):
            raise _Yield(next_item.label)
        elif isinstance(next_item, Except):
            raise _Raise(next_item.exception)
        else:
            raise AssertionError

    def __call__(self, *args, **kwargs) -> FunReturn:
        if self.semaphore != 0:
            raise ReentryError(repr(self.semaphore))

        self.semaphore += 1

        self.instance._process_ensure_running()

        self.instance.in_queue.put(Reset(args=args, kwargs=kwargs))
        self.instance.in_queue.put(Push())

        try:
            while True:
                try:
                    next_item = self.instance.out_queue.get(timeout=self.instance.read_timeout)
                except Empty:
                    self.instance._process_ensure_stopped()
                    raise TimeoutError

                try:
                    self._dispatch(next_item)
                except _Return as _:
                    return
                except _Raise as exc:
                    raise exc.exception from None
                except _Yield as exc:
                    yield exc.value
                    self.instance.in_queue.put(Push())
        finally:
            # super-important for GeneratorExit
            self.semaphore -= 1
