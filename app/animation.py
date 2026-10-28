import pandas as pd
from vidigi.prep import reshape_for_animations, generate_animation_df
from vidigi.animation import generate_animation
from vidigi.utils import create_event_position_df, EventPosition, ArrivalPosition, ExitPosition
from model import g
import time
import datetime as dt
#import datetime as dt
#from model import Trial #for debugging


def animate(logs, run=0):
    start_time = time.time()
    print(f'animation function started {time.strftime("%H:%M:%S", time.gmtime(start_time))}')

    # Vidigi only accepts a single replication. The whole log (including the warm up) is passed
    # so that patients who arrived during the warm up and are still waiting are shown
    logs = logs[logs['run_number']==run]

    STEP_SNAPSHOT_MAX = round(g.number_of_nelbeds * 1.1) # ensure this exceeds number of beds
    ANIMATION_DURATION = 10080 # run for 1 week after warmup
    WRAP_QUEUES_AT = 15
    X_TIME_UNITS = 30

    event_position_df = create_event_position_df([
        ArrivalPosition(x=-20, y=200),

        EventPosition(event='admission_wait_begins',
                      x=205, y=75,
                      label="Waiting for Admission"),

        EventPosition(event='sdec_admission_wait_begins',
                      x=205, y=475,
                      label="Waiting for Admission"),

        EventPosition(event='other_admission_wait_begins',
                      x=205, y=700,
                      label="Waiting for Admission"),

        EventPosition(event='admission_begins',
                      x=505, y=75,
                      resource='number_of_nelbeds',
                      label="Admitted"),

        ExitPosition(x=670, y=70)
    ])

    # Assign different waiting locations to 3 kinds of attendance
    prefix = logs['pathway'].map({"SDEC": "sdec_", "Other": "other_"}).fillna("")
    is_wait = logs['event'] == "admission_wait_begins"
    logs = logs.assign(event=logs['event'].where(~is_wait, prefix + logs['event']))

    reshaped_logs = reshape_for_animations(
        event_log=logs,
        every_x_time_units=X_TIME_UNITS,
        step_snapshot_max=STEP_SNAPSHOT_MAX,
        limit_duration=g.warm_up_period + ANIMATION_DURATION,
        warm_up=g.warm_up_period
    )

    # add co-ordinates to the logs
    position_logs = generate_animation_df(full_entity_df=reshaped_logs,
                                          event_position_df=event_position_df,
                                          wrap_queues_at=WRAP_QUEUES_AT,
                                          step_snapshot_max=STEP_SNAPSHOT_MAX,
                                          gap_between_entities=10, # need this and resource gap to be consistent
                                          gap_between_resources=10, # if changing this, also need to specify in generate_animation
                                          gap_between_queue_rows=30, # if changing this, also need to specify in generate_animation
                                          gap_between_resource_rows=30
                                          )

    # Assign different icons for SDEC and other
    def show_priority_icon(row):
            if "more" not in row["icon"]:
                    if row["pathway"] == "SDEC":
                            return "🔴"
                    elif row["pathway"] == "Other":
                            return "🟣"
                    else:
                            return row["icon"]
            else:
                        return row["icon"]

    position_logs = position_logs.assign(
                icon=position_logs.apply(show_priority_icon, axis=1)
                )

    # Dates are counted from the start of the run, so start the clock early enough that the first
    # frame (the end of the warm up) shows as 1 January 2025
    start_date = (dt.date(2025, 1, 1) - dt.timedelta(minutes=g.warm_up_period)).isoformat()

    animation = generate_animation(
        full_entity_df_plus_pos=position_logs.sort_values(['entity_id', 'snapshot_time']),
        event_position_df=event_position_df,
        scenario=g(),
        debug_mode=False,
        setup_mode=False, # turns on and off gridlines
        include_play_button=True,
        entity_icon_size=16,
        resource_icon_size=16,
        text_size=16,
        gap_between_resource_rows=30,
        plotly_height=800,
        frame_duration=600,
        frame_transition_duration=600,
        plotly_width=1500,
        override_x_max=600,
        override_y_max=900,
        time_display_units="dhm",
        start_date=start_date,
        display_stage_labels=False,
        custom_resource_icon='⚬',
        add_background_image="https://raw.githubusercontent.com/Countess-of-Chester-Hospital-NHS-FT/Non-Elective-Flow-Simulation/refs/heads/main/app/img/sq8.png"
    )

    stop_time = time.time()
    print(f'animation function stopped {time.strftime("%H:%M:%S", time.gmtime(stop_time))}')
    timer=stop_time-start_time
    print(f'Animation timer: {time.strftime("%H:%M:%S", time.gmtime(timer))}')

    return animation
