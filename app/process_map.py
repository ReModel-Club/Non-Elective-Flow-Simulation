import numpy as np
from vidigi.process_mapping import add_sim_timestamp, discover_dfg, dfg_to_graphviz
from model import g

ROUTES = {"ED": "Emergency Department",
          "SDEC": "Same Day Emergency Care",
          "Other": "Other routes"}


def _dfg(logs, title, time_metric, time_unit):
    # The simulation runs in minutes. For hours, convert the times so that vidigi's
    # durations and labels are all in the chosen unit
    divisor = 60 if time_unit == "hours" else 1
    logs = logs.assign(time=logs["time"] / divisor)
    log = add_sim_timestamp(logs, time_unit=time_unit, warm_up=g.warm_up_period / divisor)
    nodes, edges = discover_dfg(log, time_unit=time_unit, run_col_name="run_number")
    return dfg_to_graphviz(nodes, edges,
                           time_unit=time_unit,
                           time_metric=time_metric,
                           title=title,
                           show_between_run_ci=False,
                           wrap_node_labels_at=25)


def make_dfgs(logs, split_by_route=False, split_by_renege=False, time_metric="mean",
              time_unit="hours", run=None):
    """Directly-follows graphs of the patient journey, built with vidigi.

    Returns a dict of {label: graphviz.Digraph}. With `split_by_route` there is one graph for
    each route patients arrive by (ED, SDEC, Other), and with `split_by_renege` there is one
    graph for patients who reneged and one for those who didn't. Using both gives a graph for
    each combination. Otherwise there is a single graph for everyone. Groups with no patients
    are left out.
    Times on the arrows are shown in `time_unit` ("hours" or "minutes").
    The warm up period is discarded. All runs are combined unless `run` gives the number of a
    single run to show.
    """
    if run is not None:
        logs = logs[logs["run_number"] == run]
    everyone = np.full(len(logs), True)
    # Patient ids restart in each run, so a patient is identified by both run and id
    reneged = (logs["event"].eq("renege")
               .groupby([logs["run_number"], logs["entity_id"]])
               .transform("any")
               .to_numpy(dtype=bool))
    route_groups = ([(label, (logs["pathway"] == route).to_numpy())
                     for route, label in ROUTES.items()]
                    if split_by_route else [("All", everyone)])
    renege_groups = ([("Reneged", reneged), ("Did not renege", ~reneged)]
                     if split_by_renege else [(None, everyone)])
    dfgs = {}
    for route_label, in_route in route_groups:
        for renege_label, in_renege_group in renege_groups:
            in_group = in_route & in_renege_group
            if not in_group.any():
                continue
            label = route_label if renege_label is None else f"{route_label} - {renege_label}"
            dfgs[label] = _dfg(logs[in_group], f"Arrival Route: {label}",
                               time_metric, time_unit)
    return dfgs
