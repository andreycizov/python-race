# 2024-03-02

- Integrate with Celery such that `.delay` would create a new process in the current execution and thus for example 
  if we start with 2 processes running, we'll end up with 3 processes running if a new one started.
- Run a functional test with iwoca-django codebase
- Add a graphviz example of what the tool actually doses

# 2023-12-31

- The most important bit:
  - Run a functional test with iwoca-django codebase
- Combine with `race.generator.thread` and `race.generator.trace` to be able to do transactional testing in Django
- Find a way to expose the results of the executions to the user
  - Hooks that are exposed for the beginning/end of the execution
  - Spanning tree of executions, but without repeating edges 
- Can I integrate processes that are triggered by actions of other processes in this framework?
  - Would be needed to model Celery retry mechanism

# 2023-07-20

## Executor
-  Enable context switching when executing a path
-  Make path execution iterative, i.e. do not provide a full Path but just PathItem for only single yield
-  Do not raise in path executor, always return - helps with thinking about the data model because we can type it

## Visitor
-  we should be able to optimise this path by always trying to finish the available path,
   i.e. if it's not finished we continue with DPS/BFS until we reach the end of the path,
   (prioritising appropriately) until we have reached a terminal state
   from the tests in the test suite we see about 80% of incomplete scenarios for even the most
   simple issues
   (depends on Executor being iterative)


## Remote generator
-  Add protocol feature that does not need to restart the remote process every time
   we instantiate a new race