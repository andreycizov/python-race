# convert an arbitrary callable into a generator yielding all lines of execution

import inspect
import itertools
import logging
import sys
from contextlib import contextmanager
from typing import Any, Callable

from dataclasses import dataclass, field

from race2.multiprocessing.yield_fun import yield_fun_yield

_LOG = logging.getLogger(__name__)


@dataclass
class TraceYield:
    fun: Callable

    filename_lineno_label: dict[tuple[str, int, str], int] = field(default_factory=dict)
    ctr: itertools.count = field(default_factory=itertools.count)

    def get_label(self, filename: str, lineno: int, extra: str = "") -> int:
        key = (filename, lineno, extra)
        if key not in self.filename_lineno_label:
            self.filename_lineno_label[key] = next(self.ctr)

        return self.filename_lineno_label[key]

    def tracer(self, frame, event, arg=None):
        frame_info = inspect.getframeinfo(frame)

        if event == "call":
            if frame.f_code.co_name != self.fun.__name__:
                return None
            return self.tracer
        elif event == "line":
            yield_fun_yield(self.get_label(frame_info.filename, frame_info.lineno))
            return self.tracer
        elif event == "return":
            yield_fun_yield(self.get_label(frame_info.filename, frame_info.lineno, "r"))
            return
        elif event == "exception":
            return self.tracer
        else:
            raise NotImplementedError(repr(event))

    def __call__(self, *args, **kwargs) -> Any:
        sys.settrace(self.tracer)
        try:
            return self.fun(*args, **kwargs)
        finally:
            sys.settrace(None)
