from model import g

WAIT = dict(first_event="admission_wait_begins", second_event="admission_begins")

# Time in the simulation is in minutes. Queue and occupancy are sampled this often
SNAPSHOT_EVERY = 360
# The warm up check covers the whole run, and the queue is slow to work out, so sample it daily
WARM_UP_QUEUE_SNAPSHOT_EVERY = 1440  # one day

MINUTES_PER_DAY = 1440

DEVIATION_THRESHOLD = 0.05
LIGHT_BLUE = "#636efa"  # plotly's first default colour, used for the line in the top plot of vidigi's replication analysis


def _strengthen_run_lines(fig):
    # vidigi draws each run very faintly (opacity 0.2) beneath the mean line, which is hard to read
    for trace in fig.data:
        if trace.opacity is not None and trace.opacity < 0.5:
            trace.opacity = 0.7
            trace.line.width = 1.5
    return fig


def _queue_size(trial_logger):
    fig = trial_logger.plot_queue_size(
        ["admission_wait_begins"],
        limit_duration=g.warm_up_period + g.sim_duration,
        every_x_time_units=SNAPSHOT_EVERY,
        warm_up=g.warm_up_period,
    )
    return _strengthen_run_lines(fig)


def _bed_occupancy(trial_logger):
    fig = trial_logger.plot_resource_utilisation_over_time(
        every_x_time_units=SNAPSHOT_EVERY,
        warm_up=g.warm_up_period,
        limit_duration=g.warm_up_period + g.sim_duration,
        scenario={"nelbeds": g.number_of_nelbeds},
        resource_map={"admission_begins": "nelbeds"},
        as_proportion=True,
    )
    return _strengthen_run_lines(fig)


def _wait_distribution(trial_logger):
    return trial_logger.plot_duration_distribution(
        **WAIT,
        kind="box",
        split_by="pathway",
        title="Time waiting for admission (minutes)",
    )


def _wait_by_arrival_time(trial_logger):
    return trial_logger.plot_metric_vs_arrival_time(
        **WAIT,
        colour_by="pathway",
        rolling_window=50,
        warm_up=g.warm_up_period,
        marker_size=3,
    )


def _add_warm_up_line(fig, x):
    # vidigi doesn't mark the warm up period on its diagnostic plots, so it is added here
    fig.add_vline(
        x=x,
        line_dash="dash",
        line_color="red",
        annotation_text="Warm-up period ends",
        annotation_position="top left",
    )
    return fig


def _warm_up_time_plot(fig):
    """Show a warm up diagnostic against time in days (the simulation runs in minutes)."""
    for trace in fig.data:
        trace.x = trace.x / MINUTES_PER_DAY
    fig.update_xaxes(title_text="Time (days)")
    return _add_warm_up_line(fig, g.warm_up_period / MINUTES_PER_DAY)


def _warm_up_queue(trial_logger):
    fig = trial_logger.plot_warm_up_diagnostic(
        series="queue",
        event="admission_wait_begins",
        limit_duration=g.warm_up_period + g.sim_duration,
        every_x_time_units=WARM_UP_QUEUE_SNAPSHOT_EVERY,
    )
    return _warm_up_time_plot(fig)


def _warm_up_occupancy(trial_logger):
    fig = trial_logger.plot_warm_up_diagnostic(
        series="occupancy",
        event="admission_begins",
        limit_duration=g.warm_up_period + g.sim_duration,
        every_x_time_units=SNAPSHOT_EVERY,
    )
    return _warm_up_time_plot(fig)


def _warm_up_wait(trial_logger):
    fig = trial_logger.plot_warm_up_diagnostic(
        series="duration",
        **WAIT,
        limit_duration=g.warm_up_period + g.sim_duration,
        every_x_time_units=SNAPSHOT_EVERY,
    )
    # This plot is not against time but against the nth patient to arrive (for those who were
    # admitted), so the warm up is shown as the number of such patients arriving during it
    df = trial_logger.to_dataframe()
    admitted = df.loc[df["event"] == "admission_begins", "entity_id"]
    arrivals = df[(df["event"] == "arrival") & (df["entity_id"].isin(admitted))]
    n_in_warm_up = (
        arrivals[arrivals["time"] <= g.warm_up_period]
        .groupby("run_number")
        .size()
        .mean()
    )
    return _add_warm_up_line(fig, n_in_warm_up)


def _replication_analysis(trial_logger):
    fig = trial_logger.plot_replication_analysis(
        **WAIT, what="mean", deviation_threshold=DEVIATION_THRESHOLD
    )
    # Match the relative half-width (bottom) line to the line in the top plot
    deviation_trace = next(t for t in fig.data if t.name == "deviation")
    deviation_trace.line.color = LIGHT_BLUE
    deviation_trace.marker.color = LIGHT_BLUE
    return fig


def _explain_replications(trial_logger):
    """Interpretation of the replication analysis, which depends on what the results show.

    Returns (is_problem, markdown).
    """
    precision = trial_logger.get_replication_precision(
        **WAIT, deviation_threshold=DEVIATION_THRESHOLD
    )
    n_runs = len(precision)
    final_deviation = precision["deviation"].iloc[-1]
    enough = precision.loc[precision["stays_below_threshold"], "n_replications"]

    basics = f"""
The **relative half-width** (the bottom plot, also called the deviation) is the width of the
confidence interval around the average wait, as a proportion of that average. A value of
{DEVIATION_THRESHOLD} means we are 95% confident the true average is within
{DEVIATION_THRESHOLD:.0%} of the average from the runs. It normally falls as runs are added.
You have enough runs once it falls below the red dashed line and **stays** below it.
"""
    if not enough.empty:
        return (
            False,
            basics
            + f"""
**What this shows:** the deviation stays below {DEVIATION_THRESHOLD} from {int(enough.min())} runs
onwards. You have run {n_runs}, so you have enough runs for the average wait to be reliable to
within {DEVIATION_THRESHOLD:.0%}.
""",
        )
    runs_needed = ""
    if final_deviation == final_deviation:  # not NaN
        # The interval narrows roughly in proportion to 1 / sqrt(runs)
        estimate = int(n_runs * (final_deviation / DEVIATION_THRESHOLD) ** 2) + 1
        runs_needed = (
            f" With {n_runs} runs the deviation is {final_deviation:.2f}, and as a "
            f"rough guide it would take around {estimate} runs to reach "
            f"{DEVIATION_THRESHOLD}."
        )
    return (
        True,
        basics
        + f"""
**What this shows:** the deviation never stays below {DEVIATION_THRESHOLD} in the {n_runs} runs
you have, so the average wait is not yet pinned down to within {DEVIATION_THRESHOLD:.0%}.
{runs_needed}

Things to try or consider:
- **Run more simulations.** This is the usual fix, but the gain gets smaller each time.
- **Accept less precision.** If a wider margin is fine for your purpose, the current deviation
  tells you how reliable the average is.
- **Check the system is stable.** If demand is close to or above the number of beds, the queue
  keeps growing, so waits depend on how long the simulation runs and the average never settles
  however many runs you add. Check the bed occupancy and queue plots, and the warm-up checks.
- **Check the warm-up period.** If it is too short, runs start from an unrepresentative state
  and the averages are pulled around.
- **Remember waits vary a lot.** Waits that are mostly short with some very long ones are slow
  to average out, so many runs may be needed.
""",
    )


# {name shown to the user: details of the plot}
#   plot: function building the plot
#   description: short text shown above the plot
#   warning: optional text shown as a warning above the plot
#   explain: optional function returning (is_problem, markdown) for a "how to interpret this" box
PLOTS = {
    "Queue size over time": dict(
        plot=_queue_size,
        description="Number of patients waiting for a bed, for each run.",
    ),
    "Bed occupancy over time": dict(
        plot=_bed_occupancy, description="Proportion of beds in use, for each run."
    ),
    "Distribution of waits for admission": dict(
        plot=_wait_distribution,
        description="How long patients waited for a bed, by route of arrival, across all runs. "
        "The box shows the middle half of waits, the line inside it is the median.",
    ),
    "Waits by arrival time": dict(
        plot=_wait_by_arrival_time,
        description="How the wait for admission changes with the time patients arrive, by "
        "route of arrival.",
    ),
}

# Plots for checking the model rather than for understanding its results
UNSTABLE_WARNING = (
    "Depending on your system, this may never stabilise - for example if demand is close to or "
    "above what the beds can cope with - so the queue keeps growing. In that case, primarily "
    "consider the bed occupancy plot when deciding on the warm-up period."
)

DEVELOPER_PLOTS = {
    "Warm-up check: bed occupancy": dict(
        plot=_warm_up_occupancy,
        description="Use to judge whether the warm-up period is long enough: bed occupancy "
        "should have levelled off by the end of the warm-up period (the red line).",
    ),
    "Warm-up check: queue size": dict(
        plot=_warm_up_queue,
        description="Use to judge whether the warm-up period is long enough: the queue should "
        "have levelled off by the end of the warm-up period (the red line).",
        warning=UNSTABLE_WARNING,
    ),
    "Warm-up check: waits for admission": dict(
        plot=_warm_up_wait,
        description="Use to judge whether the warm-up period is long enough: waits for "
        "admission should have levelled off by the end of the warm-up period (the "
        "red line). This is shown against the nth patient to arrive, not against "
        "time.",
        warning=UNSTABLE_WARNING,
    ),
    "Are there enough runs?": dict(
        plot=_replication_analysis,
        description="How the mean wait for admission settles as more runs are added.",
        explain=_explain_replications,
    ),
}


def make_trial_plot(trial_logger, name):
    return {**PLOTS, **DEVELOPER_PLOTS}[name]["plot"](trial_logger)
