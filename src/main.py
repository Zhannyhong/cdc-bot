import datetime
import os
import sys
import time

sys.path.insert(0, os.getcwd())

from src.website_handler import handler

from src.utils.common import utils
from src.utils.log import Log
from src.utils.captcha.two_captcha import Captcha as TwoCaptcha
from src.utils.notifications.notification_manager import NotificationManager

if __name__ == "__main__":
    config = utils.load_config_from_yaml_file(file_path="config.yaml")
    program_config = config["program_config"]

    log = Log(directory="logs", name="cdc-helper", config=config["log_config"])
    captcha_solver = TwoCaptcha(log=log, config=config["two_captcha_config"])
    notification_manager = NotificationManager(log=log, mail_config=config["mail_config"],
                                               telegram_config=config["telegram_config"])

    if not os.path.exists("temp"):
        os.makedirs("temp")
    else:
        utils.clear_directory("temp", log)

    while True:
        with handler(
                login_credentials=config["cdc_login_credentials"],
                captcha_solver=captcha_solver,
                log=log,
                notification_manager=notification_manager,
                browser_config=config["browser_config"],
                program_config=program_config
        ) as cdc_handler:

            success_logging_in = cdc_handler.account_login()
            monitored_types = program_config["monitored_types"]

            try:
                while True:
                    cdc_handler.open_booking_overview()
                    cdc_handler.get_booked_lesson_date_time()
                    cdc_handler.get_reserved_lesson_date_time()

                    for monitor_type, monitor_active in monitored_types.items():
                        if monitor_active and cdc_handler.open_field_type_booking_page(field_type=monitor_type):
                            cdc_handler.get_all_session_date_times(field_type=monitor_type)
                            cdc_handler.get_all_available_sessions(field_type=monitor_type)
                            cdc_handler.check_if_earlier_available_sessions(field_type=monitor_type)

                    log.info(cdc_handler)
                    cdc_handler.flush_notification_update()

                    if program_config["refresh_rate"] > 0:
                        refresh_rate = program_config["refresh_rate"]

                        current_time = datetime.datetime.now()
                        sleep_duration = datetime.timedelta(seconds=refresh_rate)
                        next_run_time = current_time + sleep_duration

                        # Sleep between 3 and 6 am because slots rarely get cancelled then
                        if 3 <= next_run_time.hour < 6:
                            extra_sleep = next_run_time.replace(hour=6) - next_run_time
                            sleep_duration += extra_sleep

                        cdc_handler.log.info(
                            f"Program now sleeping for {sleep_duration} till {current_time + sleep_duration}...")

                        sleep_duration = sleep_duration.total_seconds()
                        if sleep_duration > 60:
                            for i in range(int(sleep_duration / 60)):
                                cdc_handler.check_logged_in()
                                time.sleep(60)
                            time.sleep(sleep_duration % 60)
                        else:
                            time.sleep(sleep_duration)

                        cdc_handler.log.info(f"Program now resuming! Cached log in ?: {cdc_handler.logged_in}")
                    else:
                        break
            except KeyboardInterrupt:
                log.info("Program stopped by user.")
            except Exception as e:
                log.error(f"Program encountered an error: {e}")
                notification_manager.send_notification_all(title="", msg=f"Program encountered an error: {e}")
            finally:
                cdc_handler.account_logout()
                # cdc_handler.driver.quit()

                if not program_config["auto_restart"]:
                    break

                sleep_duration = datetime.timedelta(hours=1)
                message = f"Program restarting in {sleep_duration} at {datetime.datetime.now() + sleep_duration}..."
                notification_manager.send_notification_all(title="", msg=message)
                log.info(message +
                         "\n# ------------------------------------- - ------------------------------------ #\n\n")
                time.sleep(sleep_duration.total_seconds())
                continue

    log.info("Program exited.")
    notification_manager.send_notification_all(title="", msg="Program exited.")
