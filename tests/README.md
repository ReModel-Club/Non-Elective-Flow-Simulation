# Tests

This folder holds automated tests for the simulation model in [`app/`](../app/).

At present, they are just **regression tests**. Their job is to check that changes to the code
leave the model's results exactly as they were. They were written when the
project moved from version 0.0.4 of the [vidigi](https://github.com/hsma-tools/vidigi)
animation library to version 2.0.0. They are still useful after any change you
make, to check you haven't accidentally changed the model's results.

## AI use note

The regression tests in this folder were generated using Claude Opus 5.5.

They have been reviewed by a human ([Sammi Rosser](https://github.com/Bergam0t)).

## How it works

The idea is simple:

1. **Save trusted results.** We ran the model on code we knew was correct (the
   old vidigi 0.0.4 version) for a set of scenarios. We saved the outputs to
   files in [`baseline/`](baseline/). These are called the "baseline" or
   "golden" results.
2. **Compare new results.** Each time the tests run, the same scenarios are run
   on the current code. The new outputs are compared with the saved ones. If
   anything differs, the test fails and shows you where.

The model uses random sampling, but it uses fixed random seeds. That means the
same settings always give exactly the same results, so an exact comparison is
fair.

## Running the tests

First activate the project's Python environment. [pytest](https://docs.pytest.org/)
is included in `environment/requirements-dev.txt`. Then run this from the
project's root folder (the one containing `app/` and `tests/`):

```bash
pytest tests/
```

The tests take under 10 seconds. If everything is fine you will see something like:

```
============================== 9 passed in 6.12s ==============================
```

Some useful options:

| Command | What it does |
| --- | --- |
| `pytest tests/ -v` | Lists each test by name with PASSED / FAILED |
| `pytest tests/ -k r1_e0_p1` | Runs only the tests whose name contains `r1_e0_p1` |
| `pytest tests/ -x` | Stops at the first failure |

## What gets tested

### The scenarios

The model has three behaviours that can each be switched on (1) or off (0).
Each one affects how ED patients queue for a bed. (SDEC and Other patients
always get high priority.)

- **reneging**: ED patients may leave the queue without being admitted if
  they wait too long
- **escalation**: ED patients still waiting after a set time (the escalation
  threshold) are moved up to high priority
- **prioritisation**: a share of ED patients are given high priority when
  they arrive

Each combination of these is tested. That gives 2 × 2 × 2 = 8 scenarios. Each
scenario is named after its settings, e.g. `r1_e0_p1` means reneging on,
escalation off and prioritisation on. There is also a ninth scenario,
`r1_e1_p1_ed_only`, with all three switched on and only ED patients arriving
(no SDEC or Other patients).

These scenarios use a small, fast setup (40 beds, 40 simulated days, 2 runs).
That's big enough to produce queues, reneging and escalation, but quick to
run. You can see the exact settings in `FAST_CONFIG` in
[`regression_scenarios.py`](regression_scenarios.py).

### The test

[`test_regression.py`](test_regression.py) contains one test,
**`test_scenario_outputs_unchanged`**, which runs once for each of the 9
scenarios. It checks the patient-level results, the run and trial summaries,
and the full event log. The checks go from most to least important, so the
first one to fail tells you how serious the difference is. For example, if
only the last check fails, the results are the same and only the bed numbers
patients were given have changed.

The animation in the app is not tested here. Only the model's outputs are.

## The files

| File | What it is for |
| --- | --- |
| [`test_regression.py`](test_regression.py) | The tests themselves. pytest runs these. |
| [`regression_scenarios.py`](regression_scenarios.py) | Shared code: scenario definitions, running the model, and tidying ("normalising") outputs so old and new versions can be compared. |
| [`make_baseline.py`](make_baseline.py) | Script that creates the files in `baseline/`. **Not** run by pytest. |
| [`conftest.py`](conftest.py) | Loaded automatically by pytest. It lets the tests import `regression_scenarios`. |
| `baseline/*.pkl` | The saved trusted results, one file per scenario. |

## If a test fails

A failing test means the current code produces **different results** from the
baseline. It doesn't necessarily mean the new code is wrong, but you
should find out why before going further. pytest's output shows which
DataFrame differed and which columns or values didn't match.

Ask yourself:

- **Did I mean to change the model's behaviour?** For example, you changed a
  default parameter or fixed a bug in the logic. If so, a failure is expected.
  See below.
- **If not**, the change has had a side effect you didn't intend. Investigate
  before going further.

## Updating the baseline

Only regenerate the baseline when you are **sure** the new results are
correct. Regenerating replaces the trusted results with whatever the code
produces now, so any bug in it becomes the new "correct" answer.

```bash
python tests/make_baseline.py            # overwrites the files in tests/baseline/
python tests/make_baseline.py --check    # re-runs and compares, without saving anything
```

After regenerating, run `--check` to confirm the model gives the same results
every time it runs.

If you regenerate the baseline, commit the new `baseline/` files along with
the code change that caused them. In your commit message, say why the results
changed.
