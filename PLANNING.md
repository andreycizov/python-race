# 2025-03-18

- Add process "grouping" or "merging" (decide on the name), where we automatically assume that process id X and Y are the same as long as X or Y are already dead (and while they are running they are considered to be alive). It's obvious how we map a single process one-to-one, but how do we go about multiple?
  - The solution to this can be to allow the user who creates processes to remap process ids after ever process creation/deletion.

# 2025-02-25

- Create a django app setup that can be automatically tested such as [this](https://github.com/mozilla/django-piston/tree/master/tests/test_project/apps/testapp)

# 2024-07-25

- Add a de-cycler, including subgraph features of graphviz (could make it potentially easier to render really complex graphs for graphviz)
- Add a concept of a "waiter process": a dummy process that is added to the system if another process wants to wait for some time
  if the control is given to the waiter process, it would die and "activate" the process that was waiting on the timeout,
  triggering the timeout condition through temporal ordering.
- Add a "sentinel process", a process that isn't allowed to be advanced via usual means, and does not appear in `.available_processes`, 
  but is instead advanced every advance of every other process. This allows us to do checks of the global state after every transition,
  and keep it in the state. 

# 2024-07-05

- Managed to do a test run with Django using `ThreadExecutor`
- Added remote traceback passing from remote executors
- Added a process rename method that I am yet to play with for self-retrying functions.

# 2024-03-02

- Integrate with Celery such that `.delay` would create a new process in the current execution and thus for example 
  if we start with 2 processes running, we'll end up with 3 processes running if a new one started.
- Run a functional test with iwoca-django codebase
- Add a graphviz example of what the tool actually does

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
