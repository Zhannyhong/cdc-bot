import datetime
import os
import re
import sys
import time
from typing import Dict, Union

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from abstracts.cdc_abstract import CDCAbstract, Types
from src.utils.common import selenium_common


def convert_to_datetime(date_str: str, time_str: str = None):
    if time_str:
        time_str = time_str.split(' ')[0]
        return datetime.datetime.strptime(f'{date_str} | {time_str}', '%d/%b/%Y | %H:%M')
    else:
        return datetime.datetime.strptime(date_str, "%d/%b/%Y")


class handler(CDCAbstract):
    def __init__(self, login_credentials, captcha_solver, log, notification_manager, browser_config, program_config):
        browser_type = browser_config["type"] or "firefox"
        headless = browser_config["headless_mode"] or False

        if browser_type.lower() != "firefox" and browser_type.lower() != "chrome":
            log.error("Invalid browser_type was given!")
            raise Exception("Invalid BROWSER_TYPE")

        self.home_url = "https://www.cdc.com.sg"
        self.booking_url = "https://bookingportal.cdc.com.sg:"
        self.port = ""

        self.captcha_solver = captcha_solver
        self.log = log
        self.notification_manager = notification_manager

        self.browser_config = browser_config
        self.program_config = program_config

        self.auto_reserve = program_config["auto_reserve"]
        self.reserve_for_same_day = program_config["reserve_for_same_day"]

        self.username = login_credentials["username"]
        self.password = login_credentials["password"]
        self.logged_in = False
        self.notification_update_msg = ""
        self.has_slots_reserved = False

        self.platform = "linux" if "linux" in sys.platform else "windows" if "win32" in sys.platform else "osx"

        self.opening_booking_page_callback_map = {
            Types.BTT: self.open_theory_test_booking_page,
            Types.RTT: self.open_theory_test_booking_page,
            Types.FTT: self.open_theory_test_booking_page,
            Types.PRACTICAL: self.open_practical_lessons_booking_page,
            Types.SIMULATOR: self.open_simulator_lessons_booking_page,
            Types.PT: self.open_practical_test_booking_page,
        }

        options = browser_type.lower() == "firefox" and webdriver.FirefoxOptions() or webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--no-proxy-server")

        driver_name = "geckodriver" if browser_type.lower() == "firefox" else "chromedriver"
        if self.platform == "windows":
            driver_name += ".exe"
        executable_path = os.path.join("drivers", self.platform, driver_name)

        if browser_type.lower() == "firefox":
            self.driver = webdriver.Firefox(executable_path=executable_path, options=options)
        else:
            self.driver = webdriver.Chrome(executable_path=executable_path, options=options)

        self.driver.set_window_size(1600, 768)
        super().__init__(username=self.username, password=self.password, headless=headless)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.driver.close()

    def _open_index(self, path: str, sleep_delay=None):
        self.driver.get(f"{self.booking_url}{self.port}/{path}")
        if sleep_delay:
            time.sleep(sleep_delay)

    def __str__(self):
        return super().__str__()

    def reset_state(self):
        self.reset_attributes_for_all_fieldtypes()
        self.notification_update_msg = ""
        self.has_slots_reserved = False

    def is_date_in_view(self, date_str: str, field_type: str):
        return date_str in self.get_attribute_with_fieldtype("days_in_view", field_type)

    def get_earliest_time_slots(self, sessions_data: Dict, length: int, field_type: str):
        sorted_datetimes = [(date_str, time_slot) for date_str, time_slots in sessions_data.items()
                            for time_slot in time_slots]
        sorted_datetimes.sort(key=lambda comp_date: convert_to_datetime(comp_date[0], comp_date[1]))

        return_sessions_data = {}
        step = 2 if field_type == Types.SIMULATOR else 1  # No back-to-back sessions allowed for simulator lessons

        for i in range(0, min(length * step, len(sorted_datetimes)), step):
            selected_date_str, selected_time_slot = sorted_datetimes[i]

            if selected_date_str not in return_sessions_data:
                return_sessions_data[selected_date_str] = [selected_time_slot]
            else:
                return_sessions_data[selected_date_str].append(selected_time_slot)

        return return_sessions_data

    def check_if_same_sessions(self, session0: Dict, session1: Dict):
        for date_str, time_slots in session0.items():
            if date_str not in session1:
                return True

            for time_slot in time_slots:
                if time_slot not in session1[date_str]:
                    return True

        for date_str, time_slots in session1.items():
            if date_str not in session0:
                return True

            for time_slot in time_slots:
                if time_slot not in session0[date_str]:
                    return True

        return False

    def check_call_depth(self, call_depth: int):
        if call_depth > 4:
            self.account_logout()
            self.account_login()
            return False

        return True

    def check_access_rights(self, webpage: str):
        if "Alert.aspx" in self.driver.current_url:
            self.log.info(f"You do not have access to {webpage}.")
            return False

        return True

    def check_logged_in(self):
        self._open_index("NewPortal/Booking/StatementBooking.aspx")
        if self.port not in self.driver.current_url:
            self.log.info("User has been timed out! Now logging out and in again...")
            self.account_logout()
            self.account_login()
            time.sleep(0.5)

    def dismiss_normal_captcha(self, caller_identifier: str, solve_captcha: bool = False,
                               secondary_alert_timeout: int = 5, force_enabled: bool = False):
        is_captcha_present = selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_CaptchaImg",
                                                             timeout=5)
        if not is_captcha_present:
            return True

        if solve_captcha:
            success, _ = self.captcha_solver.solve(driver=self.driver, captcha_type="normal_captcha",
                                                   force_enable=force_enabled)
            if not success:
                return False

            captcha_submit_btn = selenium_common.wait_for_elem(self.driver, By.ID, "ctl00_ContentPlaceHolder1_Button1")
            captcha_submit_btn.click()
        else:
            captcha_close_btn = selenium_common.wait_for_elem(self.driver, By.CLASS_NAME, "close")
            captcha_close_btn.click()

        # dismiss alert if found
        _, alert_text = selenium_common.dismiss_alert(driver=self.driver, timeout=2)
        if "incorrect captcha" in alert_text:
            selenium_common.dismiss_alert(driver=self.driver, timeout=secondary_alert_timeout)
            self.log.info(f"Normal captcha failed for opening {caller_identifier} page.")
            return False

        return True

    def accept_terms_and_conditions(self):
        terms_checkbox = selenium_common.is_elem_present(self.driver, By.ID,
                                                         "ctl00_ContentPlaceHolder1_chkTermsAndCond")
        agree_btn = selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_btnAgreeTerms")
        if terms_checkbox and agree_btn:
            terms_checkbox.click()
            agree_btn.click()

    def get_course_data(self, course_element_id: Union[str, None] = None):
        course_selection = Select(
            self.driver.find_element(By.ID, course_element_id or "ctl00_ContentPlaceHolder1_ddlCourse"))
        number_of_options = len(course_selection.options)

        course_data = {"course_selection": course_selection, "available_courses": []}

        for option_index in range(0, number_of_options):
            option = course_selection.options[option_index]
            course_data["available_courses"].append(str(option.text.strip()))

        return course_data

    def select_course_from_name(self, course_data: Dict, course_name: str):
        for selection_idx in range(0, len(course_data["available_courses"])):
            current_course = course_data["available_courses"][selection_idx]
            if course_name in current_course:
                course_data["course_selection"].select_by_index(selection_idx)
                return selection_idx

        return False

    def select_course_from_idx(self, course_data: Dict, course_idx: int):
        if course_idx < 0 or course_idx > len(course_data["available_courses"]):
            self.log.error(f"Course selected is out of range. {course_data['available_courses']}")
            return False

        course_data["course_selection"].select_by_index(course_idx)
        return course_data["available_courses"][course_idx]

    def open_home_page(self, sleep_delay: Union[int, None] = None):
        self.driver.get(self.home_url)
        assert "ComfortDelGro" in self.driver.title

        if sleep_delay:
            time.sleep(sleep_delay)

    def account_login(self):
        self.open_home_page(sleep_delay=2)

        prompt_login_btn = selenium_common.wait_for_elem(self.driver, By.XPATH, "//*[@id='top-menu']/ul/li[10]/a")
        prompt_login_btn.click()

        learner_id_input = selenium_common.wait_for_elem(self.driver, By.NAME, "userId")
        password_input = selenium_common.wait_for_elem(self.driver, By.NAME, "password")

        learner_id_input.send_keys(self.username)
        password_input.send_keys(self.password)

        success, _ = self.captcha_solver.solve(driver=self.driver, captcha_type="recaptcha_v2")
        if success:
            login_btn = selenium_common.wait_for_elem(self.driver, By.ID, "BTNSERVICE2")
            login_btn.click()

            _, alert_text = selenium_common.dismiss_alert(driver=self.driver, timeout=5)
            if "complete the captcha" in alert_text:
                self.log.info("Wrong captcha given.")
                self.account_logout()
                time.sleep(1)
                return self.account_login()
            else:
                url_digits = re.findall(r'\d+', self.driver.current_url)
                if len(url_digits) > 0:
                    self.port = str(url_digits[-1])
                    self.logged_in = True
                    return True
                else:
                    self.account_logout()
                    time.sleep(1)
                    return self.account_login()

    def account_logout(self):
        self._open_index("NewPortal/logOut.aspx?PageName=Logout")
        self.log.info("Logged out.")
        self.logged_in = False

    def open_booking_overview(self):
        self.check_logged_in()
        self._open_index("NewPortal/Booking/Dashboard.aspx")
        selenium_common.dismiss_alert(driver=self.driver, timeout=5)

    # TODO: check if practical sessions bookings recorded correctly
    def get_reserved_lesson_date_time(self):
        rows = self.driver.find_elements(By.CSS_SELECTOR, "table#ctl00_ContentPlaceHolder1_gvReserved tr")

        for row in rows:
            td_cells = row.find_elements(By.TAG_NAME, "td")
            if len(td_cells) > 0:
                lesson_name = td_cells[4].text

                field_type = (
                    Types.SIMULATOR if "SIMULATOR" in lesson_name else
                    Types.PRACTICAL if "Lesson" in lesson_name else
                    Types.PRACTICAL if "2BL" in lesson_name else
                    Types.PRACTICAL if "ONETEAM" in lesson_name else
                    Types.BTT if "BTT" in lesson_name else
                    Types.RTT if "RTT" in lesson_name else
                    Types.FTT if "FTT" in lesson_name else
                    Types.PT if "PT" in lesson_name else
                    None
                )

                if field_type and field_type != Types.PRACTICAL:
                    self.set_attribute_with_fieldtype("lesson_name", field_type, lesson_name)
                    reserved_sessions = self.get_attribute_with_fieldtype("reserved_sessions", field_type)

                    if td_cells[0].text not in reserved_sessions:
                        reserved_sessions.update(
                            {td_cells[0].text: [f"{td_cells[2].text[:-3]} - {td_cells[3].text[:-3]}"]})
                    else:
                        reserved_sessions[td_cells[0].text].append(f"{td_cells[2].text[:-3]} - {td_cells[3].text[:-3]}")

    def get_booked_lesson_date_time(self):
        rows = self.driver.find_elements(By.CSS_SELECTOR, "table#ctl00_ContentPlaceHolder1_gvBooked tr")

        for row in rows:
            td_cells = row.find_elements(By.TAG_NAME, "td")
            if len(td_cells) > 0:
                lesson_name = td_cells[4].text

                field_type = (
                    Types.SIMULATOR if "SIMULATOR" in lesson_name else
                    Types.PRACTICAL if "Lesson" in lesson_name else
                    Types.PRACTICAL if "2BL" in lesson_name else
                    Types.PRACTICAL if "ONETEAM" in lesson_name else
                    Types.BTT if "BTT" in lesson_name else
                    Types.RTT if "RTT" in lesson_name else
                    Types.FTT if "FTT" in lesson_name else
                    Types.PT if "PT" in lesson_name else
                    None
                )

                if field_type:
                    self.set_attribute_with_fieldtype("lesson_name", field_type, lesson_name)
                    booked_sessions = self.get_attribute_with_fieldtype("booked_sessions", field_type)

                    if td_cells[0].text not in booked_sessions:
                        booked_sessions.update(
                            {td_cells[0].text: [f"{td_cells[2].text[:-3]} - {td_cells[3].text[:-3]}"]})
                    else:
                        booked_sessions[td_cells[0].text].append(f"{td_cells[2].text[:-3]} - {td_cells[3].text[:-3]}")

    def open_field_type_booking_page(self, field_type: str):
        return self.opening_booking_page_callback_map[field_type](field_type)

    def open_theory_test_booking_page(self, field_type: str, call_depth: int = 0):
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingTT.aspx", sleep_delay=1)

        if not self.check_access_rights("NewPortal/Booking/BookingTT.aspx"):
            self.log.debug(f"User does not have {field_type.upper()} as an available option.")
            return False

        if not self.dismiss_normal_captcha(caller_identifier=f"{field_type.upper()} Booking", solve_captcha=False):
            return self.open_theory_test_booking_page(field_type, call_depth + 1)

        time.sleep(0.5)
        self.accept_terms_and_conditions()

        test_name_element = selenium_common.wait_for_elem(self.driver, By.ID,
                                                          "ctl00_ContentPlaceHolder1_lblResAsmBlyDesc")
        test_name = test_name_element.text
        return (
                (field_type == Types.BTT and "Basic Theory Test" in test_name)
                or (field_type == Types.RTT and "Riding Theory Test" in test_name)
                or (field_type == Types.FTT and "Final Theory Test" in test_name)
        )

    def open_practical_lessons_booking_page(self, field_type: str, call_depth: int = 0):
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingPL.aspx", sleep_delay=1)

        if not self.check_access_rights("NewPortal/Booking/BookingPL.aspx"):
            self.log.debug(f"User does not have {field_type.upper()} as an available option.")
            return False

        course_data = self.get_course_data()
        if len(course_data["available_courses"]) <= 1:
            self.log.error(f"No {field_type.upper()} courses available.")
            return False

        if not (self.select_course_from_name(course_data, "Class 3A Motorcar") or
                self.select_course_from_idx(course_data, 1)):
            self.log.error("Could not a select course.")
            return False

        if not self.dismiss_normal_captcha(caller_identifier="Practical Lessons Booking", solve_captcha=True):
            return self.open_practical_lessons_booking_page(field_type, call_depth + 1)

        time.sleep(2)
        if selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_lblFullBookMsg"):
            self.log.info("No available practical lessons currently.")
            self.notification_manager.send_notification_all(title="", msg="No available practical lessons currently")
            return False

        # Check if the user is able to book from other teams
        if selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_ddlOthTeamID"):
            available_teams = self.get_course_data("ctl00_ContentPlaceHolder1_ddlOthTeamID")

            if self.program_config["book_from_other_teams"] and len(available_teams["available_courses"]) > 1:
                self.get_all_session_date_times(Types.PRACTICAL)
                self.get_all_available_sessions(Types.PRACTICAL)

                available_teams_str = ""

                for idx in range(1, len(available_teams["available_courses"])):
                    available_teams = self.get_course_data("ctl00_ContentPlaceHolder1_ddlOthTeamID")
                    if len(available_teams["available_courses"]) > idx:
                        selected_team = self.select_course_from_idx(available_teams, idx)
                        available_teams_str += "=======================\n"
                        available_teams_str += f"{selected_team} has slots:\n\n"
                        time.sleep(1)

                        loading_element = selenium_common.wait_for_elem(self.driver, By.ID,
                                                                        "ctl00_ContentPlaceHolder1_UpdateProgress1")
                        while loading_element.is_displayed():
                            time.sleep(0.5)

                        team_available_sessions = {}
                        self.get_all_available_sessions(Types.PRACTICAL, team_available_sessions)

                        for available_date_str, available_time_slots in team_available_sessions.items():
                            available_teams_str += f"{available_date_str}:\n"
                            for time_slot in available_time_slots:
                                available_teams_str += f"  -> {time_slot}\n"
                        available_teams_str += "=======================\n"

                        self.get_all_session_date_times(Types.PRACTICAL)
                        self.get_all_available_sessions(Types.PRACTICAL)

                self.notification_manager.send_notification_all(
                    title=f"SESSIONS FROM OTHER TEAMS DETECTED",
                    msg=available_teams_str
                )

        return True

    def open_simulator_lessons_booking_page(self, field_type: str, call_depth: int = 0):
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingSimulator.aspx", sleep_delay=1)

        if not self.check_access_rights("NewPortal/Booking/BookingSimulator.aspx"):
            self.log.debug(f"User does not have {field_type.upper()} as an available option.")
            return False

        course_data = self.get_course_data()
        if len(course_data["available_courses"]) <= 1:
            self.log.error(f"No {field_type.upper()} courses available.")
            return False

        if not (self.select_course_from_name(course_data, "Simulator Course - Car (School)") or
                self.select_course_from_idx(course_data, 1)):
            self.log.error("Could not a select course.")
            return False

        if not self.dismiss_normal_captcha(caller_identifier="Simulator Lessons Booking", solve_captcha=True):
            return self.open_simulator_lessons_booking_page(field_type, call_depth + 1)

        time.sleep(2)
        return True

    def open_practical_test_booking_page(self, field_type: str, call_depth: int = 0):
        if "REVISION" in self.lesson_name_practical:
            self.log.info("No practical lesson available for user, seems user has completed practical lessons")
            return False

        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingPT.aspx", sleep_delay=1)

        if not self.check_access_rights("NewPortal/Booking/BookingPT.aspx"):
            self.log.debug(f"User does not have {field_type.upper()} as an available option.")
            return False

        if not self.dismiss_normal_captcha(caller_identifier="Practical Test Booking", solve_captcha=True):
            return self.open_practical_test_booking_page(field_type, call_depth + 1)

        time.sleep(0.5)
        self.accept_terms_and_conditions()
        return True

    def get_all_session_date_times(self, field_type: str):
        for row in self.driver.find_elements(By.CSS_SELECTOR, "table#ctl00_ContentPlaceHolder1_gvLatestav tr"):
            th_cells = row.find_elements(By.TAG_NAME, "th")

            selected_times_array = self.get_attribute_with_fieldtype("times_in_view", field_type)
            selected_days_array = self.get_attribute_with_fieldtype("days_in_view", field_type)

            for i in range(2, len(th_cells)):
                selected_time_str = str(th_cells[i].text).split("\n")[1]
                if selected_time_str not in selected_times_array:
                    selected_times_array.append(selected_time_str)

            td_cells = row.find_elements(By.TAG_NAME, "td")
            if td_cells:
                selected_day_str = td_cells[0].text
                if selected_day_str not in selected_days_array:
                    selected_days_array.append(selected_day_str)

    def get_all_available_sessions(self, field_type: str, local_tb: Dict = None):
        input_elements = self.driver.find_elements(By.TAG_NAME, "input")
        last_practical_input_element = None
        has_booked_lessons_in_view = False

        for input_element in input_elements:
            # Images1.gif -> available slot
            # Images2.gif -> reserved slot
            # Images3.gif -> booked slot
            input_element_src = input_element.get_attribute("src")
            if any(gif in input_element_src for gif in ["Images1.gif", "Images2.gif", "Images3.gif"]):
                # e.g. ctl00_ContentPlaceHolder1_gvLatestav_ctl02_btnSession4 (02 is row, 4 is column)
                element_id = str(input_element.get_attribute("id"))
                element_id_spliced = element_id.split('_')
                # row = int(element_id_spliced[3][-2:]) - 2
                column = int(element_id_spliced[-1][10:]) - 1

                parent_table = input_element.find_element(By.XPATH, "../../..")
                parent_row = input_element.find_element(By.XPATH, "../..")
                td_cells = parent_row.find_elements(By.TAG_NAME, "td")

                tr_rows = parent_table.find_elements(By.TAG_NAME, "tr")
                th_cells = tr_rows[0].find_elements(By.TAG_NAME, "th")

                available_session_date = td_cells[0].text
                start_col = 4 if field_type == Types.SIMULATOR else 2
                available_session_time = str(th_cells[column + start_col].text).split("\n")[1]

                web_elements_in_view = {} if local_tb is not None else self.get_attribute_with_fieldtype(
                    "web_elements_in_view", field_type)
                web_element_key = f"{available_session_date} : {available_session_time}"
                if web_element_key not in web_elements_in_view:
                    web_elements_in_view.update({web_element_key: element_id})

                if "Images1.gif" in input_element_src:
                    available_sessions = local_tb if local_tb is not None else self.get_attribute_with_fieldtype(
                        "available_sessions", field_type)

                    last_practical_input_element = (
                        input_element if field_type in [Types.PRACTICAL, Types.PT, Types.SIMULATOR] else None
                    )

                    if available_session_date not in available_sessions:
                        available_sessions.update({available_session_date: [available_session_time]})
                    elif available_session_time not in available_sessions[available_session_date]:
                        available_sessions[available_session_date].append(available_session_time)
                elif "Images2.gif" in input_element_src:
                    pass
                elif "Images3.gif" in input_element_src:
                    has_booked_lessons_in_view = True

        booked_sessions = self.get_attribute_with_fieldtype("booked_sessions", field_type)
        if last_practical_input_element is None or has_booked_lessons_in_view or booked_sessions:
            return

        # check if sessions can be booked, else skip (e.g.
        # practical: no PDL for lesson 6
        # pt: simulator modules not done
        # simulator: 5th practical lesson not done)
        last_practical_input_element_id = last_practical_input_element.get_attribute("id")
        try:
            self.log.info(f"Attempting to reserve a session to check if user can book {field_type.upper()}")
            last_practical_input_element.click()
            WebDriverWait(self.driver, 5).until(EC.alert_is_present())

            alert = self.driver.switch_to.alert
            self.log.warning(f"User can't book {field_type.upper()} because '{alert.text}'")
            self.set_attribute_with_fieldtype("can_book_next", field_type, False)
            alert.accept()
        except selenium_common.TimeoutException:
            # if no alert, means user could book session. Now we have to unreserve it again.
            self.driver.find_element(By.ID, last_practical_input_element_id).click()
            self.log.info("Reverted reservation of session successfully")
            time.sleep(2)

    def create_notification_update(self, field_type: str):
        earlier_sessions = self.get_attribute_with_fieldtype("earlier_sessions", field_type)
        booked_sessions = self.get_attribute_with_fieldtype("booked_sessions", field_type)
        reserved_sessions = self.get_attribute_with_fieldtype("reserved_sessions", field_type)

        notif_msg = ""

        notif_msg += "\n=======================\n"
        notif_msg += f"{field_type.upper()} UPDATE\n"
        notif_msg += "=======================\n\n"

        notif_msg += "--------------------------\n"
        notif_msg += "Booked sessions:\n"
        for booked_date_str, booked_time_slots in booked_sessions.items():
            notif_msg += f"{booked_date_str}:\n"
            for time_slot in booked_time_slots:
                notif_msg += f"  -> {time_slot}\n"
        notif_msg += "--------------------------\n"

        notif_msg += "--------------------------\n"
        notif_msg += "Reserved sessions:\n"
        for reserved_date_str, reserved_time_slots in reserved_sessions.items():
            notif_msg += f"{reserved_date_str}:\n"
            for time_slot in reserved_time_slots:
                self.has_slots_reserved = True
                notif_msg += f"  -> {time_slot}\n"
        notif_msg += "--------------------------\n\n"

        notif_msg += "Available sessions:\n"
        for earlier_date_str, earlier_time_slots in earlier_sessions.items():
            notif_msg += f"{earlier_date_str}:\n"
            for time_slot in earlier_time_slots:
                notif_msg += f"  -> {time_slot}\n"
            notif_msg += "\n"
        notif_msg += "\n"

        self.notification_update_msg += notif_msg

        return notif_msg

    def update_earlier_sessions(self, field_type: str):
        available_sessions = self.get_attribute_with_fieldtype("available_sessions", field_type)

        booked_sessions = self.get_attribute_with_fieldtype("booked_sessions", field_type)
        earlier_sessions = {}

        if len(booked_sessions.keys()) > 0:
            for available_date_str, available_time_slots in available_sessions.items():
                available_date = convert_to_datetime(available_date_str)

                for booked_date_str in booked_sessions:
                    booked_date = convert_to_datetime(booked_date_str)

                    valid_booked_date = (available_date < booked_date) or (
                            self.reserve_for_same_day and available_date == booked_date)
                    if valid_booked_date and available_date_str not in earlier_sessions:
                        earlier_sessions[available_date_str] = list(available_time_slots)

            self.set_attribute_with_fieldtype("earlier_sessions", field_type, dict(earlier_sessions))
        else:
            self.set_attribute_with_fieldtype("earlier_sessions", field_type, dict(available_sessions))

    def flush_notification_update(self):
        if self.notification_update_msg != "":
            self.notification_manager.send_notification_all(
                title=f"{datetime.datetime.now()}",
                msg=self.notification_update_msg
            )

            if self.has_slots_reserved:
                self.notification_manager.send_notification_all(
                    title=f"RESERVED SLOTS DETECTED",
                    msg="You have outstanding slots reserved! "
                        "Please log in to the website and confirm these reservations else they will be forfeited."
                )
        self.reset_state()

    def check_if_earlier_available_sessions(self, field_type: str):
        self.update_earlier_sessions(field_type)

        available_sessions = self.get_attribute_with_fieldtype("available_sessions", field_type)
        web_elements_in_view = self.get_attribute_with_fieldtype("web_elements_in_view", field_type)

        earlier_sessions = self.get_attribute_with_fieldtype("earlier_sessions", field_type)
        reserved_sessions = self.get_attribute_with_fieldtype("reserved_sessions", field_type)

        if not self.check_if_same_sessions(self.get_attribute_with_fieldtype("cached_earlier_sessions", field_type),
                                           earlier_sessions):
            return False

        number_of_slots_needed = self.program_config["slots_per_type"][field_type]
        if self.auto_reserve and number_of_slots_needed > 0:
            earliest_sessions_to_be_reserved = self.get_earliest_time_slots(earlier_sessions, number_of_slots_needed,
                                                                            field_type)
            to_be_removed_reservations = {}

            for reserved_date_str, reserved_time_slots in reserved_sessions.items():
                if not self.is_date_in_view(reserved_date_str, field_type):
                    number_of_slots_needed -= len(reserved_time_slots)
                    continue

                reserved_date = convert_to_datetime(reserved_date_str)

                for earliest_date_str in earliest_sessions_to_be_reserved:
                    earliest_date = convert_to_datetime(earliest_date_str)
                    if reserved_date <= earliest_date:
                        number_of_slots_needed -= len(reserved_time_slots)
                        break
                else:  # only executed if reserved date is not the earliest session
                    to_be_removed_reservations.update({reserved_date_str: []})
                    for reserved_time_slot in reserved_time_slots:
                        input_element_id = web_elements_in_view[f"{reserved_date_str} : {reserved_time_slot}"]
                        input_element = selenium_common.wait_for_elem(self.driver, By.ID, input_element_id)
                        input_element.click()

                        alert_found, alert_text = selenium_common.dismiss_alert(self.driver, timeout=10)
                        if alert_found:
                            self.log.error(
                                f"Failed to unreserve a {field_type.upper()} slot on "
                                f"{reserved_date_str} : {reserved_time_slot}. Reason: {alert_text}")
                            number_of_slots_needed -= 1
                            break
                        else:
                            self.log.info(
                                f"Successfully reserved a {field_type.upper()} slot on "
                                f"{reserved_date_str} : {reserved_time_slot}.")
                            to_be_removed_reservations[reserved_date_str].append(reserved_time_slot)

            for date_str, time_slots in to_be_removed_reservations.items():
                if date_str not in available_sessions:
                    available_sessions.update({date_str: list(time_slots)})

                for time_slot in time_slots:
                    reserved_sessions[date_str].remove(time_slot)
                    available_sessions[date_str].append(time_slot)
                if len(reserved_sessions[date_str]) == 0:
                    del reserved_sessions[date_str]

            if number_of_slots_needed > 0:
                self.log.info(f"Number of slots to reserve for {field_type.upper()} is: {number_of_slots_needed}")
                earliest_sessions_to_be_reserved = self.get_earliest_time_slots(earlier_sessions,
                                                                                number_of_slots_needed, field_type)

                for date_str, time_slots in earliest_sessions_to_be_reserved.items():
                    for time_slot in time_slots:
                        input_element_id = web_elements_in_view[f"{date_str} : {time_slot}"]
                        input_element = selenium_common.wait_for_elem(self.driver, By.ID, input_element_id)
                        input_element.click()
                        self.log.info(
                            f"Attempting to reserve a {field_type.upper()} slot on {date_str} : {time_slot}.")

                        alert_found, alert_text = selenium_common.dismiss_alert(self.driver, timeout=10)
                        if alert_found and "non-computerised" in alert_text:
                            alert_found, alert_text = selenium_common.dismiss_alert(self.driver, timeout=10)

                        if alert_found:
                            self.log.error(
                                f"Failed to reserve a {field_type.upper()} slot on {date_str} : {time_slot}. "
                                f"Reason: {alert_text}")
                            if any(e in alert_text for e in ["Store Value:", "before", "exceeded the maximum number"]):
                                break
                            elif "Back to Back session is not allowed" in alert_text:  # for simulator
                                continue
                    else:  # only executed if there is no alert
                        if date_str not in reserved_sessions:
                            reserved_sessions[date_str] = [time_slot]
                        else:
                            reserved_sessions[date_str].append(time_slot)

                        available_sessions[date_str].remove(time_slot)
                        if len(available_sessions[date_str]) == 0:
                            del available_sessions[date_str]
                        continue
                    break  # only executed if there is an alert

        self.set_attribute_with_fieldtype("reserved_sessions", field_type, dict(reserved_sessions))
        self.set_attribute_with_fieldtype("available_sessions", field_type, dict(available_sessions))
        self.update_earlier_sessions(field_type)
        self.set_attribute_with_fieldtype("cached_earlier_sessions", field_type,
                                          dict(self.get_attribute_with_fieldtype("earlier_sessions", field_type)))
        notif_msg = self.create_notification_update(field_type)
        self.log.info(
            f"There are updates to {field_type.upper()} available sessions. More info here: \n{notif_msg}")

        return True
