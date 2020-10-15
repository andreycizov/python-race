race
====

Race condition modelling package.

Known idiosyncracies
--------------------

Busy loops should only have 1 label per 1 execution of a loop.
The same thing goes for all other loops.

Otherwise we will have to interleave the loop cycle with all possible executions of the other thread.

Which is essentially a runtime multiplier.

For a process executing in a loop:

```
a, b, c, d, a, b, c, d, a, b, c, d, a, b, c, d, a
```

Even if another process is a one-label process, we
can interleave them this way:
```
a, X, b, c, d, a, b, X, c, d, a, b, c, X, d, a, b, c, d, X, a
```

