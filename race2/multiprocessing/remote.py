import json
import logging
import multiprocessing
from queue import Empty
from typing import Optional, Any, Iterable, Dict, Tuple, Callable

from dataclasses import dataclass
from tblib import Traceback

from race2.abstract import ProcessGenerator, StateID

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


class ResetOk(ParentEvent):
    pass


@dataclass
class Stop(ParentEvent):
    value: Any


@dataclass
class Next(ParentEvent):
    label: StateID


@dataclass
class Except(ParentEvent):
    exception: BaseException
    traceback_json: str

    @classmethod
    def from_exception(cls, exc: BaseException) -> "Except":
        return Except(
            exception=exc,
            traceback_json=json.dumps(Traceback(exc.__traceback__).to_dict()),
        )

    def reraise(self) -> None:
        raise self.exception.with_traceback(
            Traceback.from_dict(json.loads(self.traceback_json)).as_traceback()
        )


@dataclass
class _Yield(Exception):
    value: StateID


@dataclass
class _Raise(Exception):
    exception: Exception


@dataclass
class _Return(Exception):
    value: Any


class _Exit(Exception):
    pass


def _main_subprocess(remote_generator: "RemoteGenerator"):
    try:
        remote_generator.run()
    except:
        _LOG.exception("_main_subprocess raised")


@dataclass
class RemoteGenerator:
    # todo  ensure that we do not need to restart the remote process every time we would like to do
    #       a clean up. requires a synchronous interface for remove Termination
    fun: Callable
    in_queue: Optional[multiprocessing.Queue] = None
    out_queue: Optional[multiprocessing.Queue] = None
    process: Optional[multiprocessing.Process] = None

    iter_obj: Optional[Iterable[StateID]] = None

    join_timeout: float = 10.0
    read_timeout: Optional[float] = 1.0

    def _process_ensure_running(self):
        if self.process is None:
            self._process_start()

    def _process_ensure_stopped(self):
        if self.process is not None:
            self._process_terminate()

    def _process_start(self):
        if self.process is not None:
            raise AssertionError("process is None")

        self.in_queue = multiprocessing.Queue(maxsize=1)
        self.out_queue = multiprocessing.Queue(maxsize=1)

        self.process = multiprocessing.Process(
            target=_main_subprocess,
            args=(self,),
            name="race.mp",
            daemon=True,
        )
        self.process.start()

    def _process_terminate(self):
        if self.process is None:
            raise AssertionError("process is None")

        self.in_queue.put(Terminate())
        self.in_queue = None
        self.out_queue = None
        self.process.terminate()
        self.process.join(timeout=self.join_timeout)
        self.process = None

    def __enter__(self) -> "RemoteGenerator":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self):
        self._process_ensure_running()

    def close(self):
        self._process_ensure_stopped()

    def client(self) -> "RemoteGeneratorClient":
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
            raise AssertionError("self.iter_obj is None")

        try:
            next_item = next(self.iter_obj)
        except StopIteration as exc:
            self.out_queue.put(Stop(exc.value))
        except Exception as exc:
            self.out_queue.put(Except.from_exception(exc))
        else:
            self.out_queue.put(Next(next_item))

    def _dispatch_reset(self, msg: Reset):
        try:
            self.iter_obj = self.fun(*msg.args, **msg.kwargs)
        except Exception as exc:
            self.out_queue.put(Except.from_exception(exc))
        else:
            self.out_queue.put(ResetOk())

    def _dispatch_terminate(self, msg: Terminate):
        raise _Exit()

    def run(self):
        try:
            while True:
                next_msg = self.in_queue.get()

                self._dispatch(next_msg)
        except _Exit:
            pass
        except BaseException as exc:
            _LOG.exception("main_child")
            self.out_queue.put(Except(exc))
        finally:
            _LOG.info("terminating")

    def __call__(self, *args, **kwargs):
        return self.client().__call__(*args, **kwargs)


class ReentryError(Exception):
    pass


class RemoteTimeoutError(Exception):
    pass


@dataclass
class RemoteGeneratorClient:
    instance: RemoteGenerator
    semaphore: int = 0

    def _dispatch(self, next_item: Any):
        if isinstance(next_item, Stop):
            raise _Return(next_item.value)
        elif isinstance(next_item, Next):
            raise _Yield(next_item.label)
        elif isinstance(next_item, Except):
            next_item.reraise()
        else:
            raise AssertionError

    def __call__(self, *args, **kwargs) -> ProcessGenerator:
        if self.semaphore != 0:
            raise ReentryError(repr(self.semaphore))

        self.semaphore += 1

        self.instance._process_ensure_running()

        self.instance.in_queue.put(Reset(args=args, kwargs=kwargs))

        try:
            next_item = self.instance.out_queue.get(timeout=self.instance.read_timeout)
        except Empty:
            self.instance._process_ensure_stopped()
            raise RemoteTimeoutError

        if isinstance(next_item, Except):
            next_item.reraise()
        elif isinstance(next_item, ResetOk):
            self.instance.in_queue.put(Push())
        else:
            raise AssertionError(repr(next_item))

        try:
            while True:
                try:
                    next_item = self.instance.out_queue.get(
                        timeout=self.instance.read_timeout
                    )
                except Empty:
                    self.instance._process_ensure_stopped()
                    raise RemoteTimeoutError

                try:
                    self._dispatch(next_item)
                except _Return as rtn:
                    return rtn.value
                except _Yield as exc:
                    yield exc.value
                    self.instance.in_queue.put(Push())
        finally:
            # super-important for GeneratorExit
            self.instance.in_queue.put(Terminate())

            self.semaphore -= 1
