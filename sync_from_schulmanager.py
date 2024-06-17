"""This module is used to sync the schedule from the schulmanager website."""

import os
import json
import logging
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


def convert(html_content) -> dict:
    """Converts a html string into a dictionary"""
    dicts = html_to_json.convert(html_content)
    return dicts

def combine_entries(entries) -> list:
    """Combines entries that are double entries into one entry with a start and end time."""
    combined_entries = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        while i + 1 < len(entries) and entries[i]['subject'] == entries[i + 1]['subject']:
            entry['double'] = True
            entry['end'] = entries[i + 1]['end']
            i += 1
        combined_entries.append(entry)
        i += 1
    return combined_entries

def get_exception_details(entry) -> dict:
    """Returns the details of an exception entry."""
    if 'is-new' in entry['_attributes']['class']:
        if 'span' in entry and 'span' in entry['span'][0]:
            subject = entry['span'][0]['span'][0]['_value']
            room = entry['div'][0]['span'][0]['span'][0]['_value']
            teacher = entry['span'][1]['span'][0]['span'][0]['_value']
        else:
            subject = entry['div'][0]['_value']
            room = "No room specified"
            teacher = entry['div'][1]['span'][0]['span'][0]['_value']
    elif 'cancelled' in entry['_attributes']['class']:
        subject = entry['span'][0]['_value']
        room = entry['div'][0]['span'][0]['span'][0]['_value']
        teacher = entry['span'][1]['span'][0]['span'][0]['_value']
    else:
        subject = entry['span'][0]['visual-diff'][0]['span'][0]['_value']
        room = entry['div'][0]['span'][0]['span'][1]['_value']
        teacher = entry['span'][1]['span'][0]['span'][0]['_value']

    return {
        'subject': subject,
        'room': room,
        'teacher': teacher,
        "cancelled": "cancelled" in entry['_attributes']['class']}

def load_schedule_from_json(jsondata):
    """Loads a schedule from a json string."""
    # SO EIN MÜLL DER SOURCE CODE SIEHT AUS WIE NACH NER ATOMBOMBE
    schedule_raw = json.loads(jsondata)
    schedule = {
        "monday": [],
        "tuesday": [],
        "wednesday": [],
        "thursday": [],
        "friday": [],
        "exceptions": []
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
        "IF G2": "Informatik GK 2"
    }

    time_table = [[[7, 50], [8, 35]], [[8, 35], [9, 20]], [[9, 40], [10, 25]], [[10, 30], [11, 15]], [[11, 35], [12, 20]], [[12, 20], [13, 5]], [[13, 30], [14, 15]], [[14, 20], [15, 5]], [[15, 10], [15, 55]], [[15, 55], [16, 40]], [[16, 40], [17, 25]], [[17, 25], [18, 10]]]

    # hours from 1 to 12
    for i,hour in enumerate(schedule_raw["tbody"][0]["tr"]):
        for j, lesson_data in enumerate(hour["td"]):
            lesson = None
            try:
                lesson = lesson_data["div"][0]["div"][0]["div"][0]
            except KeyError:
                logging.warning("No lesson found for hour %d, lesson %d", i, j)
            if lesson is None:
                continue

            new_lesson = {
                "is_exception": "is-new" in lesson["_attributes"]["class"] or "visual-diff" in lesson["span"][0] or "cancelled" in lesson["_attributes"]["class"],
                "teacher": "",
                "room": "",
                "subject": ""
            }
            if not new_lesson["is_exception"]:
                new_lesson["teacher"] = lesson["span"][1]["span"][0]["span"][0]["_value"]
                new_lesson["room"] = lesson["div"][0]["span"][0]["span"][0]["_value"]
                new_lesson["subject"] = lesson["span"][0]["span"][0]["_value"]
            else:
                lesson_data = get_exception_details(lesson)
                new_lesson["teacher"] = lesson_data["teacher"]
                new_lesson["room"] = lesson_data["room"]
                new_lesson["subject"] = lesson_data["subject"]
                if lesson_data["cancelled"]:
                    schedule["exceptions"].append({
                        "subject": lesson_data["subject"],
                        "room": lesson_data["room"],
                        "teacher": lesson_data["teacher"],
                        "day": list(schedule.keys())[j],
                        "cancelled": True
                    })

            if new_lesson["subject"] != "":
                schedule[list(schedule.keys())[j]].append({
                    "subject": subject_abbrv[new_lesson["subject"].replace("  ", " ")] if new_lesson["subject"] in subject_abbrv else new_lesson["subject"],
                    "room": new_lesson["room"],
                    "teacher": new_lesson["teacher"],
                    "double": False,
                    "start": time_table[i][0],
                    "end": time_table[i][1]
                })
    for day in schedule:
        schedule[day] = combine_entries(schedule[day])

    return schedule

def load_page_data() -> str:
    """Loads the page data from the schulmanager website"""
    load_dotenv(".env")
    webdriver_options = Options()
    webdriver_options.add_argument('-headless')

    s = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=s, options=webdriver_options)
    driver.get('https://login.schulmanager-online.de/#/modules/schedules/view//')

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "emailOrUsername")))
    username_field = driver.find_element(By.ID, 'emailOrUsername')
    password_field = driver.find_element(By.ID, 'password')
    username_field.send_keys(os.getenv('SMUSR'))
    password_field.send_keys(os.getenv('SMPW'))

    password_field.send_keys(Keys.RETURN)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "lesson-cell")))
    WebDriverWait(driver, timeout=10).until(EC.presence_of_all_elements_located((By.TAG_NAME, 'body')))

    table = driver.find_element(By.CLASS_NAME, 'calendar-table')
    table_contents = table.get_attribute('innerHTML').replace("<!---->", "")
    lines = [line for line in table_contents.splitlines() if line.strip()]
    table_contents = '\n'.join(lines)

    driver.quit()

    return table_contents

def sync_schedule():
    """Syncs the schedule from the schulmanager website"""
    page_data = load_page_data()
    json_data = json.dumps(convert(page_data), indent=4)
    schedule = load_schedule_from_json(json_data)

    with open("schedule.json", "w", encoding='utf-8') as f:
        f.write(json.dumps(schedule, indent=4, ensure_ascii=False))
