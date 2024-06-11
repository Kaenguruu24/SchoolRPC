"""This simple python program allows you to display your current lesson configured in schedule.json in Discord"""

import os
import time
import json
import datetime
from dotenv import load_dotenv
from pypresence import Presence


CLIENT = "CLIENT_ID LOADED FROM ENV FILE"

schedule = None
rpc = None

def connect_to_discord() -> Presence:
    """This tries to connect to the Discord client and returns the RPC object if successful. If not, it returns None."""
    try:
        RPC = Presence(CLIENT,pipe=0)
        RPC.connect()

        return RPC
    except Exception as e:
        print(e)
        return None

def update_rpc():
    """Updates the RPC with the current lesson"""
    while True:
        # Get current time and day
        current_time = time.localtime()
        week_day_idx = current_time.tm_wday
        current_hour = current_time.tm_hour
        current_minute = current_time.tm_min

        # Ignoring weekends
        if week_day_idx < 0 or week_day_idx > 4:
            print("This day ain't made for both of us")
            continue

        current_day = list(schedule.keys())[week_day_idx]
        current_lesson = None

        for lesson in schedule[current_day]:
            # Checking if the lesson is valid, the two week cycle is only needed because of a sports lesson that is only every second week
            if lesson["subject"] == "NONE":
                continue
            if"two_week_cycle" in lesson:
                if lesson["two_week_cycle"] == "even" and datetime.date(current_time.tm_year, current_time.tm_mon, current_time.tm_mday).isocalendar()[1] % 2 != 0:
                    print("TWC: Even week, skipping lesson")
                    continue
                if lesson["two_week_cycle"] == "odd" and datetime.date(current_time.tm_year, current_time.tm_mon, current_time.tm_mday).isocalendar()[1] % 2 == 0:
                    print("TWC: Odd week, skipping lesson")
                    continue

            # Check if lesson is currently ongoing
            current_time_minutes = current_hour * 60 + current_minute
            lesson_start_minutes = lesson["start"][0] * 60 + lesson["start"][1]
            lesson_end_minutes = lesson["end"][0] * 60 + lesson["end"][1]
            if lesson_start_minutes <= current_time_minutes <= lesson_end_minutes:
                current_lesson = lesson
                break

        # If no lesson is found, we just display something else
        if current_lesson is None:
            print("No lesson found")
            time.sleep(15)
            continue

        start_epoch = int((datetime.datetime.strptime(str(current_time.tm_year) + "-" + str(current_time.tm_mon) + "-" + str(current_time.tm_mday), "%Y-%m-%d") + datetime.timedelta(minutes=lesson_start_minutes)).timestamp())
        end_epoch = int((datetime.datetime.strptime(str(current_time.tm_year) + "-" + str(current_time.tm_mon) + "-" + str(current_time.tm_mday), "%Y-%m-%d") + datetime.timedelta(minutes=lesson_end_minutes)).timestamp())
        rpc.update(details=current_lesson["subject"], state="in Raum " + current_lesson["room"], start=start_epoch, end=end_epoch, large_image="logo", large_text="Otto-Kühne-Schule Godesberg")

        time.sleep(15)

def main():
    """Load data and wait for available client"""
    global schedule
    global rpc
    global CLIENT
    # Load data
    try:
        with open("schedule.json", encoding="utf8") as f:
            data = json.load(f)
            if "monday" not in data or "tuesday" not in data or "wednesday" not in data or "thursday" not in data or "friday" not in data:
                print("schedule.json is not a valid schedule file")
                return
            schedule = data

    except FileNotFoundError:
        print("Could not find schedule.json")
        return
    except json.JSONDecodeError:
        print("schedule.json is not a valid JSON file")
        return

    # Connect to Discord
    load_dotenv()
    CLIENT = os.getenv("CLIENT_ID")

    rpc = connect_to_discord()
    while rpc is None:
        time.sleep(15)
        rpc = connect_to_discord()

    print("Connected to Discord RPC")
    update_rpc()


main()
