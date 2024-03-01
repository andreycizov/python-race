# convert an arbitrary callable into a generator yielding all lines of execution

import inspect
import logging
import sys
from contextlib import contextmanager
from typing import Any

from dataclasses import dataclass

from race.generator.thread import thread_yield, AnyCallable

_LOG = logging.getLogger(__name__)


def tracer(frame, event, arg=None):
        if event == 'call':
            return tracer
        elif event == 'line':
            frame_info = inspect.getframeinfo(frame)

            thread_yield((frame_info.filename, frame_info.lineno))
            return tracer
        elif event == 'return':
            return
        elif event == 'exception':
            return tracer
        else:
            raise NotImplementedError(repr(event))


@contextmanager
def trace():
    sys.settrace(tracer)
    try:
        yield
    finally:
        sys.settrace(None)


@dataclass
class Trace:
    fun: AnyCallable

    def tracer(self, frame, event, arg=None):
        if event == 'call':
            if frame.f_code.co_name != self.fun.__name__:
                return None
            return tracer
        elif event == 'line':
            frame_info = inspect.getframeinfo(frame)

            thread_yield((frame_info.filename, frame_info.lineno))
            return tracer
        elif event == 'return':
            return
        elif event == 'exception':
            return tracer
        else:
            raise NotImplementedError(repr(event))

    def __call__(self, *args, **kwargs) -> Any:
        sys.settrace(self.tracer)
        try:
            return self.fun(*args, **kwargs)
        finally:
            sys.settrace(None)
