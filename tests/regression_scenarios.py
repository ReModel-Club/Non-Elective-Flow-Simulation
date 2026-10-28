"""Shared scenario definitions and helpers for the vidigi migration regression tests.

The baseline was generated on vidigi 0.0.4 (pre-migration). The same scenarios
are re-run after migration and compared against the stored outputs.

A "regression test" here means: run the model on old code and save the results,
then run the same model on new code and check the results are identical. Both
make_baseline.py (which saves results) and test_regression.py (which compares
them) import this file, so both are guaranteed to run exactly the same
scenarios in exactly the same way.
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

# The model code lives in the app/ folder, not in tests/. Work out the full
# path to app/ (two levels up from this file, then into "app") and add it to
# Python's import search path so that `from model import ...` works.
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from model import g, Trial  # noqa: E402  (needs APP_DIR on sys.path)

# Folder where the saved "golden" results are kept: tests/baseline/
BASELINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline")

# Small, fast configuration that still produces queues, reneging and escalation
# All times in the model are in minutes, so 1440 = one day (24 * 60).
FAST_CONFIG = dict(
    number_of_nelbeds=40,          # few beds, so queues form quickly
    sim_duration=40 * 1440,        # simulate 40 days
    warm_up_period=5 * 1440,       # ignore the first 5 days while the model fills up
    number_of_runs=2,              # two runs is enough to check multi-run behaviour
    mean_time_in_bed=2000,
    sd_time_in_bed=3000,
    escalation_threshold=40 * 60,  # 40 hours
)

# The matrix of switchable behaviours
# Each behaviour can be off (0) or on (1). itertools.product gives every
# combination: (0,0,0), (0,0,1), (0,1,0) ... (1,1,1), i.e. 2 x 2 x 2 = 8 scenarios.
# Testing them all makes sure no combination of settings is left unchecked.
MATRIX = [
    dict(reneging=r, escalation=e, prioritisation=p)
    for r, e, p in itertools.product([0, 1], [0, 1], [0, 1])
]


def scenario_name(overrides):
    """Turn a settings dict into a short name, e.g. {reneging: 1, escalation: 0, ...} -> "r1_e0_p0".

    The name is also used as the baseline file name (r1_e0_p0.pkl).
    """
    # .format(**overrides) fills each {placeholder} with the matching dict value
    return "r{reneging}_e{escalation}_p{prioritisation}".format(**overrides) + (
        "_ed_only" if overrides.get("sdec_inter_visit", 0) > 1e6 else ""
    )


# Build {name: settings} for all 8 scenarios in the matrix
SCENARIOS = {scenario_name(o): o for o in MATRIX}

# One extra scenario with only ED patients. Setting the average time between
# SDEC and Other arrivals to a huge number (1e7 minutes, about 19 years) means
# those patients effectively never arrive during the simulation.
_no_other = dict(reneging=1, escalation=1, prioritisation=1, sdec_inter_visit=1e7, other_inter_visit=1e7)
SCENARIOS[scenario_name(_no_other)] = _no_other


class _Config:
    """Temporarily apply settings to the global `g` class.

    The model reads its settings from attributes on the class `g` (e.g.
    g.number_of_nelbeds). Changing them affects every later run, so we must
    put the original values back afterwards, or one test could quietly change
    the settings used by the next.

    This class is a "context manager", meaning it is used with a `with` block:

        with _Config(number_of_nelbeds=10):
            ...  # g.number_of_nelbeds is 10 in here
        # back to its original value out here

    Python calls __enter__ at the start of the block and __exit__ at the end,
    even if an error happens inside the block.
    """

    def __init__(self, **settings):
        # **settings collects keyword arguments into a dict, e.g. {"number_of_nelbeds": 10}
        self.settings = settings

    def __enter__(self):
        # Remember the current values so they can be restored later
        self.saved = {k: getattr(g, k) for k in self.settings}
        # Apply the new values (setattr(g, "x", 5) is the same as g.x = 5)
        for k, v in self.settings.items():
            setattr(g, k, v)

    def __exit__(self, *exc):
        # Put the original values back
        for k, v in self.saved.items():
            setattr(g, k, v)


def run_scenario(overrides, base=FAST_CONFIG):
    """Run the model with the given settings and return its outputs, tidied for comparison.

    `overrides` holds the settings for this scenario (e.g. reneging on/off). They
    are layered on top of `base`: {**base, **overrides} merges two dicts, and
    where both contain the same key the value from `overrides` wins.
    """
    with _Config(**{**base, **overrides}):
        event_log, patient_df, run_summary_df, trial_summary_df = Trial().run_trial()
    # reset_index() turns the DataFrame's index into an ordinary column, so it
    # is compared along with the rest of the data
    return {
        "event_log": normalise_event_log(event_log),
        "patient_df": normalise_patient_df(patient_df),
        "run_summary_df": run_summary_df.reset_index(),
        "trial_summary_df": trial_summary_df.reset_index(),
    }


# --- normalisation: lets old (patient/run) and new (entity_id/run_number) logs compare ---
# "Normalising" means reshaping both the old and new outputs into one standard
# form (same column names, same column order, same row order). Then any
# difference left over is a real change in results, not just a cosmetic one.

# Old vidigi called these columns "patient" and "run"; vidigi 2 calls them
# "entity_id" and "run_number". Both are renamed to the old names.
ENTITY_COLS = ("patient", "entity_id")
RUN_COLS = ("run", "run_number")
# The columns that carry meaning. Any other columns (e.g. ones a library adds
# for its own use) are left out of the comparison.
SEMANTIC_COLS = ["run", "patient", "pathway", "event_type", "event", "time", "resource_id"]


def _rename(df):
    """Rename entity/run columns to "patient"/"run", whichever version of vidigi made the log."""
    # Work on a copy so the caller's DataFrame is not changed
    df = df.copy()
    for c in ENTITY_COLS:
        if c in df.columns:
            df = df.rename(columns={c: "patient"})
    for c in RUN_COLS:
        if c in df.columns:
            df = df.rename(columns={c: "run"})
    return df


def normalise_event_log(event_log):
    """Put an event log into a standard form so old and new logs can be compared row by row."""
    df = _rename(event_log)
    # Older logs may not have a resource_id (bed number) column at all, so add
    # an empty one (NaN = "not a number", pandas' missing value) to match
    if "resource_id" not in df.columns:
        df["resource_id"] = np.nan
    # Keep only the meaningful columns, in a fixed order
    df = df[SEMANTIC_COLS].copy()
    # vidigi 2 does not allow 'renege' under event_type 'arrival_departure', so it is logged as its
    # own event_type after migration. This is an intended change; compare on the old label.
    df.loc[df["event"] == "renege", "event_type"] = "arrival_departure"
    # Make sure bed numbers are stored as numbers (any value that isn't one becomes NaN)
    df["resource_id"] = pd.to_numeric(df["resource_id"], errors="coerce")
    # Sort into a fixed order. kind="mergesort" is a "stable" sort: rows that
    # tie on every sort column keep their original relative order, so the
    # result is the same every time.
    return df.sort_values(["run", "time", "patient", "event"], kind="mergesort").reset_index(drop=True)


def normalise_patient_df(patient_df):
    """Put the per-patient results table into a standard column naming and row order."""
    df = _rename(patient_df)
    # reset_index(drop=True) renumbers the rows 0, 1, 2... after sorting
    return df.sort_values(["run", "patient"]).reset_index(drop=True)


def drop_resource_ids(event_log):
    """Event log without bed ids: used as a fallback when only bed allocation differs."""
    return event_log.drop(columns="resource_id")


def beds_in_use_over_time(event_log):
    """Beds occupied at the time of every resource_use / resource_use_end event, per run."""
    # Keep only the rows where a patient takes or releases a bed
    df = event_log[event_log["event_type"].isin(["resource_use", "resource_use_end"])].copy()
    # Each bed taken counts +1, each bed released counts -1
    df["delta"] = np.where(df["event_type"] == "resource_use", 1, -1)
    # Several patients can take/release beds at exactly the same time, so
    # combine them into one net change per time point
    df = df.groupby(["run", "time"], as_index=False)["delta"].sum()
    # A running total of the changes gives the number of beds in use at each
    # time. It is calculated separately for each run, so runs don't add together.
    df["occupied"] = df.groupby("run")["delta"].cumsum()
    return df[["run", "time", "occupied"]].reset_index(drop=True)
