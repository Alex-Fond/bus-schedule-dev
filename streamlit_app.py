import streamlit as st
import pandas as pd
import time
import datetime
import math
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

# The functions to actually check stuff
def safety_margin(num, battery):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    bus = list_bus_number[num]
    string = f"bus_{bus}_soh"
    soh = bus_settings[string]
    battery_minimum = tool_settings["minimum_soc"]
    battery_maximum = tool_settings["maximum_soc"]
    if battery * soh < battery_minimum:
        st.write(f":red[Error]: Bus {bus} reaches below required minimum battery charge during activity {num}")
        return False
    elif battery * soh > battery_maximum:
        st.write(f":red[Error]: Bus {bus} above required maximum battery charge during activity {num}")
        return False
    return True

def validate_time(num):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    timespan = calc_time_activity(num)
    if timespan < 0:
        timespan = 0
        st.write(f":orange[Warning]: activity {num} ends before it starts (negative duration), activity ignored")
    elif timespan == 0:
        st.write(f":orange[Warning]: activity {num} ends at the same time as it starts (duration of 0), activity ignored")

def calc_battery(num, prev_battery):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    bus = list_bus_number[num]
    if prev_battery == None:
        string = f"bus_{bus}_battery_start"
        prev_battery = bus_settings[string]
    string = f"bus_{bus}_battery_max"
    max_battery = bus_settings[string]
    string = f"bus_{bus}_soh"
    soh = bus_settings[string]
    timespan = calc_time_activity(num)
    if timespan < 0:
        return battery
    string = f"bus_{bus}_custom_usage"
    if bus_settings[string] == True:
        usage = list_usage[num]
    else:
        act = activity[num]
        if act == bus_settings["idle_name"]:
            string = f"bus_{bus}_idle"
            usage = bus_settings[string]
        elif act == bus_settings["charge_name"]:
            usage = -1 * calc_charging_speed(num)
        else:
            string = f"bus_{bus}_active"
            usage = bus_settings[string]
    battery_change = usage * timespan
    battery = prev_battery - (battery_change / (max_battery * soh))
    return battery

def calc_charging_speed(num):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    bus = list_bus_number[num]
    string = f"bus_{bus}_custom_usage"
    if bus_settings[string] == True:
        return usage[num]
    else:
        battery = list_battery[num]
        if battery <= tool_settings["optimal_charge"][1] and battery >= tool_settings["optimal_charge"][0]:
            timetil = calc_time_until_perc(bus, battery, tool_settings["optimal_charge"][1], tool_settings["charge_speed_optimal"])
            timespan = calc_time_activity(num)
            if timespan <= timetil:
                return tool_settings["charge_speed_optimal"]
            else:
                speed = ((timespan * tool_settings["charge_speed_optimal"]) + ((timetil-timespan) * tool_settings["charge_speed_suboptimal"])) / (timespan + timetil)
                return speed
        elif battery >= tool_settings["optimal_charge"][1]:
            return tool_settings["charge_speed_suboptimal"]
        elif battery <= tool_settings["optimal_charge"][0]:
            timetil = calc_time_until_perc(bus, battery, tool_settings["optimal_charge"][0], tool_settings["charge_speed_suboptimal"])
            timespan = calc_time_activity(num)
            if timespan <= timetil:
                return tool_settings["charge_speed_suboptimal"]
            else:
                speed = ((timespan * tool_settings["charge_speed_suboptimal"]) + ((timetil-timespan) * tool_settings["charge_speed_optimal"])) / (timespan + timetil)
                return speed

def calc_time_until_perc(bus, battery, charge, charge_speed):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    string = f"bus_{bus}_soh"
    soh = bus_settings[string]
    string = f"bus_{bus}_battery_max"
    max_charge = bus_settings[string]
    dif = (charge - battery) * max_charge * soh
    timespan = dif/charge_speed
    return timespan

def calc_time_activity(num):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    start_time_list = str(list_start_time_long[num]).split()
    if len(start_time_list) == 1:
        start_time_list.append("00:00:00")
    start_time = start_time_list[0] + " " + start_time_list[1]
    end_time_list = str(list_end_time_long[num]).split()
    if len(end_time_list) == 1:
        end_time_list.append("00:00:00")
    end_time = end_time_list[0] + " " + end_time_list[1]
    start = datetime.datetime(*time.strptime(start_time, "%Y-%m-%d %H:%M:%S")[0:6])
    end = datetime.datetime(*time.strptime(end_time, "%Y-%m-%d %H:%M:%S")[0:6])
    difference = end - start
    timespan = difference.total_seconds()/60/60
    return timespan

def calc_charge_time_minimum(num):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    bus = list_bus_number[num]
    charging = False
    string = f"bus_{bus}_custom_usage"
    if bus_settings[string] == True:
        usage = list_usage[num]
        if usage < 0:
            charging = True
        else:
            charging = False
    else:
        act = list_activity_name[num]
        if act == bus_settings["charge_name"]:
            charging = True
        else:
            charging = False
    if charging == True:
        check = calc_time_activity(num) >= tool_settings["min_charge_time"]/60
        if check == False:
            st.write(f":red[Error]: Bus {bus} is charging for less than the required amount of time during activity {num}")
    else:
        return True

def check_overlap(num, prev_act):
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    start_time_list = str(list_start_time_long[num]).split()
    if len(start_time_list) == 1:
        start_time_list.append("00:00:00")
    start_time = start_time_list[0] + " " + start_time_list[1]
    end_time_list = str(list_end_time_long[num]).split()
    if len(end_time_list) == 1:
        end_time_list.append("00:00:00")
    end_time = end_time_list[0] + " " + end_time_list[1]
    start = datetime.datetime(*time.strptime(start_time, "%Y-%m-%d %H:%M:%S")[0:6])
    end = datetime.datetime(*time.strptime(end_time, "%Y-%m-%d %H:%M:%S")[0:6])
    difference = start - end
    if difference < 0:
        st.write(f":red[Error]: activity {num} starts before activity {prev_act} has ended")
        return False
    return True

def calc_dpru_dru():
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    dpru = 0
    dru = 0
    for num in range(schedule_count):
        timespan = calc_time_activity(num)
        if timespan < 0:
            timespan = 0
        dpru += timespan
        active = bus_settings["active_name"].split()
        if list_activity_name[num] == active:
            dru += timespan
    if dru == 0:
        st.write(f":red[Error]: no activities with name \"{bus_settings['active_name']}\" found with a duration greater than 0")
        return 0
    return dpru/dru

def check_error(errorless, erroring):
    if errorless == True and erroring == True:
        return True
    else:
        return False

# Full schedule check
def check_schedule():
    global progress_max, progress_current, check_progress
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    progress_max = len(df_schedule.index) + len(df_timetable.index)
    progress_current = 0
    check_progress = st.progress(progress_current)
    errorless = True
    for bus in df_schedule.bus_number.unique():
        prev_act = None
        prev_battery = None
        for activity in df_schedule.sort_values(by="start_time_long")[df_schedule.bus_number == bus]["activity_number"]:
            if validate_time(activity) == True:
                erroring = check_overlap(activity, prev_act)
                errorless = check_error(errorless, erroring)
                battery = calc_battery(activity, prev_battery)
                erroring = safety_margin(battery)
                errorless = check_error(errorless, erroring)
                erroring = calc_charge_time_minimum(activity)
                errorless = check_error(errorless, erroring)
                prev_battery = battery
            progress_current += 1
            check_progress.progress(progress_current/progress_max)
            prev_act = activity
    check_timetable()
    if errorless == True:
        chart()
    else:
        st.write("Submit a valid schedule to see the generated Gannt chart for it")
    dpru_dru = calc_dpru_dru()
    if dpru_dru != 0:
        st.write(f"Calculated DPRU/DRU ratio: {dpru_dru:.2f} used hours per productive hour")

# Full timetable check
def check_timetable():
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    global progress_max, progress_current, check_progress
    for val in range(timetable_count):
        satisfied = False
        start_location = list2_start_location[val]
        end_location = list2_end_location[val]
        start_time = list2_start_time[val]
        bus_line = list2_bus_line[val]
        for activity in df_schedule.sort_values(by="start_time_long")["activity_number"]:
            if satisfied == False:
                start_location2 = str(df_schedule.loc[df_schedule["activity_number"] == activity, "start_location"]).split()[1:-4]
                start_location2 = " ".join(start_location2)
                if start_location == start_location2:
                    end_location2 = str(df_schedule.loc[df_schedule["activity_number"] == activity, "end_location"]).split()[1:-4]
                    end_location2 = " ".join(end_location2)
                    if end_location == end_location2:
                        start_time2 = str(df_schedule.loc[df_schedule["activity_number"] == activity, "start_time"]).split()[1][:-3]
                        if start_time == start_time2:
                            bus_line2 = str(df_schedule.loc[df_schedule["activity_number"] == activity, "bus_line"]).split()[1]
                            try:
                                bus_line2 = int(bus_line2)
                            except ValueError:
                                bus_line2 = 0
                            if bus_line == bus_line2 or bus_line2 == 0:
                                satisfied = True
        if satisfied == False:
            st.write(f":red[Error]: Bus line {bus_line} from {start_location} to {end_location} at {start_time} is not accounted for")
        progress_current += 1
        check_progress.progress(progress_current/progress_max)

# Create Gannt chart
def chart():
    with open('./bus.json') as f:
        bus_settings = json.load(f)
    with open('./tool.json') as f:
        tool_settings = json.load(f)
    fig, ax = plt.subplots(figsize=(20, 10))
    busses = []
    for i in range(bus_count):
        busses.append(f"Bus {i+1}")
    max_x = datetime.datetime(*time.strptime("0001-01-01 00:00:00", "%Y-%m-%d %H:%M:%S")[0:6])
    min_x = datetime.datetime(*time.strptime("9999-12-31 23:59:59", "%Y-%m-%d %H:%M:%S")[0:6])
    for bus in busses:
        ax.barh(int(bus[4:]), 0)
        for activity in df_schedule[df_schedule.bus_number==int(bus[4:])].sort_values(by="start_time_long")["activity_number"]:
            start = str(df_schedule.loc[df_schedule["activity_number"] == activity, "start_time_long"]).split()[1:-4]
            if len(start) == 1:
                start.append("00:00:00")
            start = " ".join(start)
            start = datetime.datetime(*time.strptime(start, "%Y-%m-%d %H:%M:%S")[0:6])
            if start < min_x:
                min_x = start
            start_time = mpl.dates.date2num(start)
            end = str(df_schedule.loc[df_schedule["activity_number"] == activity, "end_time_long"]).split()[1:-4]
            if len(end) == 1:
                end.append("00:00:00")
            end = " ".join(end)
            end = datetime.datetime(*time.strptime(end, "%Y-%m-%d %H:%M:%S")[0:6])
            if end > max_x:
                max_x = end
            end_time = mpl.dates.date2num(end)
            timespan = end_time-start_time
            ax.barh(y=int(bus[4:]), width=timespan, left=start_time)
    ax.set_ylabel("Bus")
    ax.set_xlabel("Time")
    ax.set_xlim([min_x, max_x])
    ax.xaxis_date()
    ax.set_title("Gannt chart for imported bus schedule")
    ax.set_yticks(np.arange(len(busses))+1, labels=busses)
    ax.invert_yaxis()
    st.pyplot(fig=fig)
    return

# Convert the dataframes to lists
def create_lists():
    global list_start_location, list_end_location, list_start_time, list_end_time, list_activity_name, list_bus_line, list_energy_usage, list_start_time_long, list_end_time_long, list_bus_number, list2_start_location, list2_start_time, list2_end_location, list2_bus_line, schedule_count, timetable_count, list_battery
    # df_schedule
    df_timetable["bus_line"].fillna(0)
    df_schedule["bus_line"].fillna(0)
    df_timetable["index"] = range(len(df_timetable.index))
    #list_activity_number = df_schedule["activity_number"].to_list() # honestly no point in this, just use "i in range(count)" (see count vars below)
    list_start_location = df_schedule["start_location"].to_list()
    list_end_location = df_schedule["end_location"].to_list()
    list_start_time = df_schedule["start_time"].to_list()
    list_end_time = df_schedule["end_time"].to_list()
    list_activity_name = df_schedule["activity_name"].to_list()
    list_bus_line = df_schedule["bus_line"].to_list()
    list_energy_usage = df_schedule["energy_usage"].to_list()
    list_start_time_long = df_schedule["start_time_long"].to_list()
    list_end_time_long = df_schedule["end_time_long"].to_list()
    list_bus_number = df_schedule["bus_number"].to_list()
    # df_timetable
    list2_start_location = df_timetable["start_location"].to_list()
    list2_start_time = df_timetable["start_time"].to_list()
    list2_end_location = df_timetable["end_location"].to_list()
    list2_bus_line = df_timetable["bus_line"].to_list()
    # extra
    schedule_count = len(list_start_location)
    timetable_count = len(list2_start_location)
    list_battery = [0] * schedule_count
    # okay let's go
    print(schedule_count)
    check_schedule()

st.title("Bus schedule checker")

uploaded_schedule = st.file_uploader("Upload bus schedule (Excel)", type="xlsx")

if uploaded_schedule is not None:
    global df_schedule, bus_count
    df_schedule = pd.read_excel(uploaded_schedule, names=["activity_number", "start_location", "end_location", "start_time", "end_time", "activity_name", "bus_line", "energy_usage", "start_time_long", "end_time_long", "bus_number"])
    st.write(f"Loaded {uploaded_schedule.name}")
    bus_count = df_schedule["bus_number"].nunique()

uploaded_timetable = st.file_uploader("Upload timetable to satisfy (Excel)", type="xlsx")

if uploaded_timetable is not None:
    global df_timetable
    df_timetable = pd.read_excel(uploaded_timetable, names=["start_location", "start_time", "end_location", "bus_line"])
    st.write(f"Loaded {uploaded_timetable.name}")

with st.popover("Open tool settings"):
    tool_settings = json.loads("{}")
    st.write("State of Charge")
    st.write(":orange[Warning: if you set any bus to have a SoC outside of this range it will generate an error!]")
    tool_settings["minimum_soc"] = st.number_input("Minimum State of Charge (0-1)", value=0.1, min_value=0., max_value=1., step=0.05)
    tool_settings["maximum_soc"] = st.number_input("Maximum State of Charge (0-1)", value=0.9, min_value=max(0., tool_settings["minimum_soc"]), max_value=1., step=0.05)
    st.write("Charging")
    tool_settings["optimal_charge"] = st.slider("Optimal battery range for charging (0-1)", value=(0.0, 0.9), min_value=0., max_value=1., step=0.01)
    tool_settings["charge_speed_optimal"] = st.number_input("Charging speed within optimal battery range (kWh)", value=450., min_value=0., step=10.)
    tool_settings["charge_speed_suboptimal"] = st.number_input("Charging speed outside optimal battery range (kWh)", value=60., min_value=0., step=10.)
    tool_settings["min_charge_time"] = st.number_input("Minimum charge time (minutes)", value=15., min_value=0., step=5.)
    st.write("Default schedule settings")
    st.write(":orange[Warning: changing these settings below will reset their respective values in your schedule settings!]")
    default_battery = st.number_input("Default battery capacity at 100% State of Health (kWh)", value=100., min_value=0., step=10.)
    default_battery_start = st.number_input("Default battery percentage at the start of the schedule (0-1)", value=1., min_value=0., max_value=1., step=0.01)
    default_soh = st.number_input("Default State of Health (0-1)", value=0.85, min_value=0., max_value=1., step=0.05)
    default_idle = st.number_input("Default usage (kWh) - idle", value=0.01, min_value=0., step=0.01)
    default_active = st.number_input("Default usage (kWh) - active", value=10.8, min_value=0., step=1.)
    default_custom_usage = st.checkbox("By default use usage values in imported Excel sheet instead of these settings")
    with open('./tool.json', 'w') as f:
        json.dump(tool_settings, f)

with st.popover("Open schedule settings"):
    if uploaded_schedule is not None:
        bus_settings = json.loads("{}")
        st.subheader("Activity settings")
        bus_settings["active_name"] = st.text_input("Activity name - active (for DPRU/DRU)", value="dienst rit")
        bus_settings["material_name"] = st.text_input("Activity name - from/to bus hub (for KPI)", value="materiaal rit")
        bus_settings["idle_name"] = st.text_input("Activity name - idling", value="idle")
        bus_settings["charge_name"] = st.text_input("Activity name - charging", value="opladen")
        st.subheader("Bus settings")
        st.write(":blue[You can change these default values in your tool settings.]")
        for i in range(bus_count):
            st.write(f"Bus {i+1}")
            bus_string = f"bus_{i+1}_soh"
            bus_settings[bus_string] = st.number_input(f"Bus {i+1} - State of Health", value=default_soh, min_value=0., max_value=1., step=0.05)
            bus_string = f"bus_{i+1}_battery_max"
            bus_settings[bus_string] = st.number_input(f"Bus {i+1} - battery capacity at 100% State of Health (kWh)", value=default_battery, min_value=0., step=10.)
            bus_string = f"bus_{i+1}_battery_start"
            bus_settings[bus_string] = st.number_input(f"Bus {i+1} - battery percentage at the start of the schedule", value=default_battery_start, min_value=0., max_value=1., step=0.01)
            bus_string = f"bus_{i+1}_idle"
            bus_settings[bus_string] = st.number_input(f"Bus {i+1} - Usage (kWh) - idle", value=default_idle, min_value=0., step=0.1)
            bus_string = f"bus_{i+1}_active"
            bus_settings[bus_string] = st.number_input(f"Bus {i+1} - Usage (kWh) - active", value=default_active, min_value=0., step=1.)
            bus_string = f"bus_{i+1}_custom_usage"
            bus_settings[bus_string] = st.checkbox(f"Bus {i+1} - use usage values in imported Excel sheet instead of these settings", value=default_custom_usage)
        with open('./bus.json', 'w') as f:
            json.dump(bus_settings, f)
    else:
        st.write("Please upload a schedule first.")

if st.button("Check uploaded bus schedule") and uploaded_schedule != None and uploaded_timetable != None:
    create_lists()

with st.expander("How to use"):
    st.write("Upload a planning with busses and a timetable of all bus rides that need to be accounted for, following the format specified in the user manual.")
    st.write("Change the tool settings and schedule settings, using the information in the user manual. Percentages are measured from 0-1 rather than 0%-100%.")
    st.write("Once the Excel files are uploaded and the settings are adjusted correctly, click the \"Check uploaded bus schedule\" button to verify the validity of the uploaded schedule.")