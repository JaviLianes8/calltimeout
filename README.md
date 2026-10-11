# calltimeout

Run a callable with a wall-clock timeout and get a typed result or a clean
`TimeoutError`, with an honest choice of mechanism.

## Install

```
pip install calltimeout
```

## Usage

```python
from calltimeout import CallTimeout, run


def fetch() -> str:
    ...
    return "payload"


# Returns the result when the call finishes in time.
value = run(fetch, timeout=2.0)

# Raises CallTimeout (a subclass of TimeoutError) when it does not.
try:
    value = run(fetch, timeout=0.5)
except CallTimeout as exc:
    print(f"gave up after {exc.timeout} seconds")

# Or hand back a fallback instead of raising.
value = run(fetch, timeout=0.5, default="payload")
```

Pass arguments with `args` and `kwargs`:

```python
run(pow, timeout=1.0, args=(2, 10))
run(open, timeout=1.0, args=("data.txt",), kwargs={"mode": "r"})
```

### Choosing a mechanism

`run(fn, timeout, *, mode="thread")` takes a `mode`, and the trade-off is the
whole point of the library, so it is stated plainly:

- `mode="thread"` (default) runs the call in a daemon thread and stops waiting
  after the timeout. It is cheap and keeps everything in one process, but it
  **cannot kill a stuck, non-cooperative call**. A call that ignores the clock
  (a tight CPU loop, a blocking C call without a timeout) keeps running in the
  background after `run` has already raised; the thread lingers until it returns
  on its own or the process exits.
- `mode="process"` runs the call in a child process and **truly terminates it**
  on overrun, so a runaway call actually stops. The cost is that the callable,
  its arguments and its result must be picklable, and a process carries more
  overhead than a thread.

```python
# Truly stops a runaway call. The target must be picklable (defined at module level).
run(crunch_numbers, timeout=5.0, mode="process", args=(dataset,))
```

Zero dependencies: only the standard library (`threading`, `multiprocessing`).

## Why

Running a function under a timeout is a common need, but the usual packages have
gone stale and ship no type information:

- [`func-timeout`](https://pypi.org/project/func-timeout/): last release 2019.
- [`stopit`](https://pypi.org/project/stopit/): last release 2018.
- [`timeout-decorator`](https://pypi.org/project/timeout-decorator/): last
  release 2020.

Beyond age, most of them hide the mechanism and quietly imply they can always
cancel the work, which a thread cannot. `calltimeout` is small, fully typed
(`mypy --strict`, `py.typed`), depends on nothing, and makes the thread versus
process trade-off an explicit choice rather than a hidden surprise.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
