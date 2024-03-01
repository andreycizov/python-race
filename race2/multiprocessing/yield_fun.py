import threading
from typing import Any


class Yield:
    def __call__(self, label: int) -> None:
        pass


_LOCAL = threading.local()
_LOCAL.yield_fun: Yield | None = None


def _thread_ensure_local():
    if getattr(_LOCAL, 'yield_fun', None) is None:
        _LOCAL.yield_fun = None


def yield_fun_set(thread_gen: Yield) -> None:
    _thread_ensure_local()

    if _LOCAL.yield_fun is not None:
        raise AssertionError

    _LOCAL.yield_fun = thread_gen


def yield_fun_clean() -> None:
    _thread_ensure_local()

    if _LOCAL.yield_fun is None:
        raise AssertionError

    _LOCAL.yield_fun = None


def yield_fun_yield(label: int) -> Any:
    _thread_ensure_local()

    if _LOCAL.yield_fun is None:
        raise AssertionError

    return _LOCAL.yield_fun(label=label)
