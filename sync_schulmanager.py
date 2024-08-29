"""This module is used to sync the schedule from the schulmanager website."""

import os
import json
import glob
from datetime import datetime
from datetime import timedelta
import html_to_json
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
from webdriver_manager.firefox import GeckoDriverManager


def list_md_files(directory):
    """Lists all markdown files in a directory."""
    if not directory.endswith("/"):
        directory += "/"
    md_files = glob.glob(os.path.join(directory, "*.md"))

    return md_files


def convert(html_content) -> dict:
    """Converts a html string into a dictionary"""
    dicts = html_to_json.convert(html_content)
    return dicts


def clean_up_schedule(entries) -> list:
    """Combines entries that are double entries into one entry with a start and end time."""
    time_table = [
        [[7, 50], [8, 35]],
        [[8, 35], [9, 20]],
        [[9, 40], [10, 25]],
        [[10, 30], [11, 15]],
        [[11, 35], [12, 20]],
        [[12, 20], [13, 5]],
        [[13, 30], [14, 15]],
        [[14, 20], [15, 5]],
        [[15, 10], [15, 55]],
        [[15, 55], [16, 40]],
        [[16, 40], [17, 25]],
        [[17, 25], [18, 10]],
    ]
    combined_entries = []
    i = 0
    while i < len(entries):
        if i + 1 < len(entries):
            current_entry_index = time_table.index(
                [entries[i]["start"], entries[i]["end"]]
            )
            next_entry_index = time_table.index(
                [entries[i + 1]["start"], entries[i + 1]["end"]]
            )

            lesson_to_append = None
            if next_entry_index - current_entry_index > 1:
                lesson_to_append = {
                    "subject": "NONE",
                    "start": time_table[current_entry_index + 1][0],
                    "end": time_table[current_entry_index + 1][1],
                }
        entry = entries[i]
        if i + 1 < len(entries) and entries[i]["subject"] == entries[i + 1]["subject"]:
            entry["double"] = True
            entry["end"] = entries[i + 1]["end"]
            combined_entries.append(entry)
            i += 1

        if lesson_to_append is not None:
            combined_entries.append(lesson_to_append)
        i += 1

    return combined_entries


def get_exception_details(entry) -> dict:
    """Returns the details of an exception entry."""
    if "is-new" in entry["_attributes"]["class"]:
        if "span" in entry and "span" in entry["span"][0]:
            if entry["span"][0]["span"][0]["_value"] == "Klausur":
                return {"subject": "", "room": "", "teacher": "", "cancelled": False}
            subject = entry["span"][0]["span"][0]["_value"]
            room = entry["div"][0]["span"][0]["span"][0]["_value"]
            teacher = entry["span"][1]["span"][0]["span"][0]["_value"]
        else:
            subject = entry["div"][0]["_value"]
            room = "No room specified"
            teacher = entry["div"][1]["span"][0]["span"][0]["_value"]
    elif "cancelled" in entry["_attributes"]["class"]:
        subject = entry["span"][0]["_value"]
        room = entry["div"][0]["span"][0]["span"][0]["_value"]
        teacher = entry["span"][1]["span"][0]["span"][0]["_value"]
    else:
        subject = entry["span"][0]["visual-diff"][0]["span"][0]["_value"]
        room = entry["div"][0]["span"][0]["span"][1]["_value"]
        teacher = entry["span"][1]["span"][0]["span"][0]["_value"]

    return {
        "subject": subject,
        "room": room,
        "teacher": teacher,
        "cancelled": "cancelled" in entry["_attributes"]["class"],
    }


def load_schedule_from_json(jsondata) -> dict:
    """Loads a schedule from a json string."""
    # SO EIN MÜLL DER SOURCE CODE SIEHT AUS WIE NACH NER ATOMBOMBE
    schedule_raw = json.loads(jsondata)
    schedule = {
        "monday": [],
        "tuesday": [],
        "wednesday": [],
        "thursday": [],
        "friday": [],
        "exceptions": [],
    }

    subject_abbrv = {
        "MU G1": "Musik GK 1",
        "PH L1": "Physik LK 1",
        "E5 G3": "Englisch GK 3",
        "PA G1": "Pädagogik GK 1",
        "GE G2": "Geschichte GK 2",
        "M L2": "Mathematik LK 2",
        "E5 P1": "Englisch PJK 1",
        "D G4": "Deutsch GK 4",
        "SP G5": "Sport GK 5",
        "KR G1": "Religion GK 1",
        "IF G2": "Informatik GK 2",
        "SW ZK": "Sozialwissenschaften ZK 2",
    }

    time_table = [
        [[7, 50], [8, 35]],
        [[8, 35], [9, 20]],
        [[9, 40], [10, 25]],
        [[10, 30], [11, 15]],
        [[11, 35], [12, 20]],
        [[12, 20], [13, 5]],
        [[13, 30], [14, 15]],
        [[14, 20], [15, 5]],
        [[15, 10], [15, 55]],
        [[15, 55], [16, 40]],
        [[16, 40], [17, 25]],
        [[17, 25], [18, 10]],
    ]

    # hours from 1 to 12
    for i, hour in enumerate(schedule_raw["tbody"][0]["tr"]):
        for j, lesson_data in enumerate(hour["td"]):
            lesson = None
            try:
                lesson = lesson_data["div"][0]["div"][0]["div"][0]
            except KeyError:
                # logging.warning("No lesson found for hour %d, lesson %d", i, j)
                pass
            if lesson is None:
                continue

            new_lesson = {
                "is_exception": "is-new" in lesson["_attributes"]["class"]
                or "visual-diff" in lesson["span"][0]
                or "cancelled" in lesson["_attributes"]["class"],
                "teacher": "",
                "room": "",
                "subject": "",
            }
            if not new_lesson["is_exception"]:
                new_lesson["teacher"] = lesson["span"][1]["span"][0]["span"][0][
                    "_value"
                ]
                new_lesson["room"] = lesson["div"][0]["span"][0]["span"][0]["_value"]
                new_lesson["subject"] = lesson["span"][0]["span"][0]["_value"]
            else:
                lesson_data = get_exception_details(lesson)
                new_lesson["teacher"] = lesson_data["teacher"]
                new_lesson["room"] = lesson_data["room"]
                new_lesson["subject"] = lesson_data["subject"]
                if lesson_data["cancelled"]:
                    if lesson_data["subject"] == "":
                        continue
                    schedule["exceptions"].append(
                        {
                            "subject": lesson_data["subject"],
                            "room": lesson_data["room"],
                            "teacher": lesson_data["teacher"],
                            "day": list(schedule.keys())[j],
                            "cancelled": True,
                        }
                    )

            if new_lesson["subject"] != "":
                schedule[list(schedule.keys())[j]].append(
                    {
                        "subject": (
                            subject_abbrv[new_lesson["subject"].replace("  ", " ")]
                            if new_lesson["subject"].replace("  ", " ") in subject_abbrv
                            else new_lesson["subject"]
                        ),
                        "room": new_lesson["room"],
                        "teacher": new_lesson["teacher"],
                        "double": False,
                        "start": time_table[i][0],
                        "end": time_table[i][1],
                    }
                )

    for day in schedule:
        if day == "exceptions":
            continue
        schedule[day] = clean_up_schedule(schedule[day])

    return schedule


def clean_up_assignments(assignments, schedule) -> dict:
    """Cleans up the assignments and adds them to the calendar."""
    events = []

    existing_assignments = []

    for file in list_md_files("C:/Users/Kaenguruu/Desktop/Schule/export/"):
        with open(file, "r", encoding="utf-8") as f:
            data = f.read()
            if "isAssignment: true" in data:
                existing_assignments.append({"": ""})

    for assignment in assignments:
        for event in existing_assignments:
            if (
                assignment["task"] == event["description"]
                and assignment["subject"] == event["name"]
            ):
                break
        else:
            start_timestamp = datetime.fromtimestamp(assignment["start"])
            end_timestamp = get_next_lesson_for_assignment(assignment, schedule)
            if (
                end_timestamp is None
                or abs((datetime.now() - start_timestamp).days) >= 42
            ):
                continue
            print(assignment["subject"])
            new_event = {
                "name": assignment["subject"]
                + " <"
                + datetime.fromtimestamp(assignment["start"]).strftime("%d.%m")
                + " - "
                + end_timestamp.strftime("%d.%m")
                + ">",
                "description": assignment["task"],
                "date": {
                    "day": start_timestamp.day,
                    "month": start_timestamp.month - 1,
                    "year": start_timestamp.year,
                },
                "id": "ID_task_"
                + str(hash(assignment["task"] + assignment["subject"])),
                "note": None,
                "category": next(
                    (
                        d
                        for d in data["calendars"][0]["categories"]
                        if d["name"] == assignment["subject"]
                    ),
                    {"id": None},
                )["id"],
                "formulas": [
                    {
                        "type": "interval",
                        "number": 1,
                        "timespan": "days",
                    }
                ],
                "end": {
                    "year": end_timestamp.year,
                    "month": end_timestamp.month - 1,
                    "day": end_timestamp.day,
                },
            }
            if any(
                event["name"] == new_event["name"]
                and event["description"] == new_event["description"]
                for event in events
            ):
                continue
            else:
                events.append(new_event)
    data["calendars"][0]["events"].extend(events)
    return data


def load_homework_from_json(jsondata, schedule) -> dict:
    """Loads the homework from a json string."""
    homework_raw = json.loads(jsondata)
    # Extract date from the JSON
    date_str = homework_raw["div"][0]["div"][0]["_value"]
    date_obj = datetime.strptime(date_str.split(", ")[1], "%d.%m.%Y")
    timestamp = int(date_obj.timestamp())

    subject_abbrv = {
        "Musik": "Musik GK 1",
        "Physik": "Physik LK 1",
        "Englisch": "Englisch GK 3",
        "Erziehungswissenschaft": "Pädagogik GK 1",
        "Geschichte": "Geschichte GK 2",
        "Mathematik": "Mathematik LK 2",
        "Deutsch": "Deutsch GK 4",
        "Sport": "Sport GK 5",
        "Katholische Religionslehre": "Religion GK 1",
        "Informatik": "Informatik GK 2",
        "Englisch PJK": "Englisch PJK 1",
        "Sozialwissenschaften": "Sozialwissenschaften ZK 2",
    }

    # Extract assignments
    assignments = []
    for day in homework_raw["div"]:
        date_str = day["div"][0]["_value"]
        date_obj = datetime.strptime(date_str.split(", ")[1], "%d.%m.%Y")
        timestamp = int(date_obj.timestamp())
        for assignment in day["div"][1]["div"]:
            subject = ""
            task = ""
            try:
                subject = assignment["h4"][0]["_value"]
                task = assignment["p"][0]["span"][0]["_value"]
            except Exception as e:
                pass
            assignments.append(
                {
                    "subject": subject_abbrv[subject],
                    "task": task,
                    "start": timestamp,
                    "due": 0,
                }
            )

    return clean_up_assignments(assignments, schedule)


def get_next_lesson_for_assignment(assignment, schedule) -> datetime:
    """Returns the next lesson for an assignment."""
    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    while (
        weekdays[0]
        != datetime.fromtimestamp(assignment["start"]).strftime("%A").lower()
    ):
        weekdays.append(weekdays.pop(0))
    weekdays.append(weekdays.pop(0))

    next_seven_days = []

    for day in weekdays:
        if day == "saturday" or day == "sunday":
            continue
        next_seven_days.append(schedule[day])
        for lesson in schedule[day]:
            for exception in schedule["exceptions"]:
                if (
                    lesson["subject"] == exception["subject"]
                    and exception["cancelled"]
                    and exception["day"] == day
                ):
                    continue
            if lesson["subject"] == assignment["subject"]:
                idx = weekdays.index(day) + 1
                return datetime.fromtimestamp(assignment["start"]) + timedelta(days=idx)

    return None


def load_page_data() -> str:
    """Loads the page data from the schulmanager website"""
    load_dotenv(".env")
    webdriver_options = Options()
    webdriver_options.add_argument("-headless")

    s = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=s, options=webdriver_options)
    driver.get("https://login.schulmanager-online.de/#/modules/schedules/view//")

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "emailOrUsername"))
    )
    username_field = driver.find_element(By.ID, "emailOrUsername")
    password_field = driver.find_element(By.ID, "password")
    username_field.send_keys(os.getenv("SMUSR"))
    password_field.send_keys(os.getenv("SMPW"))

    password_field.send_keys(Keys.RETURN)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "lesson-cell"))
    )
    WebDriverWait(driver, timeout=10).until(
        EC.presence_of_all_elements_located((By.TAG_NAME, "body"))
    )

    table = driver.find_element(By.CLASS_NAME, "calendar-table")
    table_contents = table.get_attribute("innerHTML").replace("<!---->", "")
    lines = [line for line in table_contents.splitlines() if line.strip()]
    table_contents = "\n".join(lines)

    driver.get("https://login.schulmanager-online.de/#/modules/classbook/homework/")

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "col-xl-6"))
    )

    homework = driver.find_element(By.CLASS_NAME, "col-xl-6")
    homework_contents = homework.get_attribute("innerHTML")

    driver.quit()

    return table_contents, homework_contents


def sync_schedule():
    """Syncs the schedule from the schulmanager website"""
    schedule_data, homework_data = load_page_data()

    schedule_json_data = json.dumps(
        convert(schedule_data), indent=4, ensure_ascii=False
    )
    schedule = load_schedule_from_json(schedule_json_data)

    homework_json_data = json.dumps(
        convert(homework_data), indent=4, ensure_ascii=False
    )
    calendar_data = load_homework_from_json(homework_json_data, schedule)
    print(calendar_data)

    with open("schedule.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(schedule, indent=4, ensure_ascii=False))


sync_schedule()
