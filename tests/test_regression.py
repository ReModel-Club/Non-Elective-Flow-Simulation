"""Regression tests: model outputs must match the pre-migration (vidigi 0.0.4) baselines.

Regenerate the baselines only with tests/make_baseline.py on trusted code.

A "regression test" checks that something which used to work still works the
same way after a change. Here, the change was upgrading the vidigi library;
these tests confirm the simulation still produces exactly the same numbers.

Run them from the project root with:

    pytest tests/

pytest finds every function whose name starts with "test_" and runs it. A test
passes if it finishes without an error, and fails if an `assert` is false or
an exception is raised.
"""

import os
import pickle

import pandas as pd
import pytest

import regression_scenarios as bs


def _load(name):
    """Load a saved baseline file from tests/baseline/ ("rb" = read binary)."""
    with open(os.path.join(bs.BASELINE_DIR, name), "rb") as f:
        return pickle.load(f)


# @pytest.mark.parametrize runs this one test function once for each value in
# the list, passing it in as `name`. So instead of writing nine near-identical
# tests (one per scenario), we write one and pytest reports nine results,
# e.g. test_scenario_outputs_unchanged[r0_e0_p0].
@pytest.mark.parametrize("name", list(bs.SCENARIOS))
def test_scenario_outputs_unchanged(name):
    # "gold" = the trusted results saved earlier; "out" = results from the current code
    gold = _load(f"{name}.pkl")
    out = bs.run_scenario(bs.SCENARIOS[name])

    # pd.testing.assert_frame_equal checks two DataFrames have the same columns,
    # rows, values and data types. If not, it fails with a message showing
    # where they differ.
    #
    # The checks are ordered from most to least important. A test stops at the
    # first failure, so the order tells you how serious a difference is: if the
    # summary tables match but a later check fails, the headline results are fine.

    # Headline results first: if only bed ids/order differ these must still hold
    pd.testing.assert_frame_equal(out["patient_df"], gold["patient_df"])
    pd.testing.assert_frame_equal(out["run_summary_df"], gold["run_summary_df"])
    pd.testing.assert_frame_equal(out["trial_summary_df"], gold["trial_summary_df"])

    # Event log without bed ids, then bed occupancy, then the full log including bed ids
    # 1. Same events at the same times, ignoring which bed number each patient got
    pd.testing.assert_frame_equal(
        bs.drop_resource_ids(out["event_log"]), bs.drop_resource_ids(gold["event_log"])
    )
    # 2. Same number of beds occupied at every point in time
    pd.testing.assert_frame_equal(
        bs.beds_in_use_over_time(out["event_log"]),
        bs.beds_in_use_over_time(gold["event_log"]),
    )
    # 3. Everything identical, including which bed each patient was given
    pd.testing.assert_frame_equal(out["event_log"], gold["event_log"])
