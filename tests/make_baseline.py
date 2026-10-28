"""Generate golden outputs. Run ONCE on the pre-migration code (vidigi 0.0.4):

python tests/make_baseline.py            # writes tests/baseline/
python tests/make_baseline.py --check    # re-runs and confirms reproducibility

A "golden" (or "baseline") output is a saved copy of what the model produced on
code we trust. Later, after changing the code, test_regression.py re-runs the same
scenarios and checks the new results still match these saved files. If they do,
we can be confident the change did not alter the model's behaviour.

This is a normal script, not a test file: pytest ignores it because its name
does not start with "test_".
"""

import os
import pickle
import sys

import pandas as pd

# Make sure Python can find regression_scenarios.py, which lives in this same
# folder, however the script is launched.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regression_scenarios as bs


def path(name):
    """Full path to a file inside the tests/baseline/ folder."""
    return os.path.join(bs.BASELINE_DIR, name)


def main(check=False):
    """Run every scenario and either save its outputs or compare against saved ones.

    check=False: write new baseline files (overwriting any that exist).
    check=True:  re-run and confirm the results match the files already saved,
                 which shows the model gives the same answer every time it runs.
    """
    # Create tests/baseline/ if it does not exist yet
    os.makedirs(bs.BASELINE_DIR, exist_ok=True)

    # SCENARIOS is a dict of {name: settings}, e.g. {"r0_e0_p0": {"reneging": 0, ...}}
    for name, overrides in bs.SCENARIOS.items():
        # `out` is a dict of four DataFrames: event_log, patient_df, run_summary_df
        # and trial_summary_df
        out = bs.run_scenario(overrides)

        # Print a short summary so you can see at a glance that each scenario
        # did something sensible (e.g. reneging only appears when it is switched on)
        el = out["event_log"]
        counts = el["event"].value_counts().to_dict()
        print(
            f"{name}: {len(el)} events; renege={counts.get('renege', 0)} "
            f"admissions={counts.get('admission_begins', 0)}"
        )

        if check:
            # Load the saved results and compare each DataFrame in turn.
            # assert_frame_equal raises an error describing the first
            # difference it finds, so the script stops if anything has changed.
            with open(path(f"{name}.pkl"), "rb") as f:
                gold = pickle.load(f)
            for k, v in out.items():
                pd.testing.assert_frame_equal(v, gold[k])
        else:
            # pickle saves Python objects (here, a dict of DataFrames) to a
            # file exactly as they are, so they can be loaded back later.
            # "wb" means "write binary".
            with open(path(f"{name}.pkl"), "wb") as f:
                pickle.dump(out, f)
    print("OK")


# This block only runs when the file is executed directly
# (python tests/make_baseline.py), not when it is imported by another file.
if __name__ == "__main__":
    # sys.argv is the list of words typed on the command line
    main(check="--check" in sys.argv)
