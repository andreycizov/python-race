# convert an arbitrary callable into a generator yielding all lines of execution

import inspect
import logging
import sys
from contextlib import contextmanager

from dataclasses import dataclass

from race.generator.thread import thread_yield, AnyCallable

_LOG = logging.getLogger(__name__)


def tracer(frame, event, arg=None):
    try:
        if event == 'call':
            return tracer
        elif event == 'line':
            frame_info = inspect.getframeinfo(frame)

            sys.exc_info()

            thread_yield((frame_info.filename, frame_info.lineno))
            return tracer
        elif event == 'return':
            return
        elif event == 'exception':
            return tracer
        else:
            raise NotImplementedError(repr(event))
    except:
        _LOG.getChild(tracer.__name__).exception('exception raised in tracer')
        exit()
        raise


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

    def __call__(self, *args, **kwargs):
        sys.settrace(tracer)
        try:
            return self.fun(*args, **kwargs)
        finally:
            sys.settrace(None)
