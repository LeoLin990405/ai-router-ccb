Use `dping` to test Droid connectivity.

Trigger conditions (any one):
- User explicitly asks to check droid status/connection
- dask hangs or Droid seems unresponsive

Execution:
- `dping` - test connectivity: `Bash(dping)`

Output: stdout = status message, exit code 0 = OK, 1 = failure
