class selenium_common:
    import selenium
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    def wait_for_elem(driver: selenium.webdriver, locator_type: str, locator: str, timeout: int = 5):
        return selenium_common.WebDriverWait(driver, timeout).until(
            selenium_common.EC.presence_of_element_located((locator_type, locator)))

    def is_elem_present(driver: selenium.webdriver, locator_type: str, locator: str, timeout: int = 2):
        try:
            return selenium_common.wait_for_elem(driver, locator_type, locator, timeout)
        except selenium_common.TimeoutException:
            return False

    def dismiss_alert(driver: selenium.webdriver, timeout: int = 2):
        alert_txt = ""
        try:
            selenium_common.WebDriverWait(driver, timeout).until(selenium_common.EC.alert_is_present())
            alert = driver.switch_to.alert
            if alert:
                alert_txt = alert.text
                alert.accept()

        except Exception as e:
            return False, str(e)
        else:
            return True, alert_txt


class utils:
    import shutil, os, yaml
    from datetime import date, datetime

    class DEFAULT_LOG:
        def info(*args):
            print("[INFO]", utils.concat_tuple(args))

        def debug(*args):
            print("[DEBUG]", utils.concat_tuple(args))

        def error(*args):
            print("[ERROR]", utils.concat_tuple(args))

        def warn(*args):
            print("[WARN]", utils.concat_tuple(args))

    def load_config_from_yaml_file(file_path: str, log=DEFAULT_LOG):
        if not utils.os.path.isfile(file_path):
            raise Exception(f"No file found at {file_path}")
        with open(file_path) as stream:
            config = {}
            try:
                config = utils.yaml.safe_load(stream)
            except utils.yaml.YAMLError as exception:
                log.error(exception)
            return config

    def init_config_with_default(config: dict, default_config: dict):
        for configValue, configType in enumerate(default_config):
            if not utils.check_key_existence_in_dict(config, configType):
                config[configType] = configValue
        return config

    def check_key_value_pair_exist_in_dict(dic, key, value):
        try:
            return dic[key] == value
        except KeyError:
            return False

    def check_key_existence_in_dict(dic, key):
        try:
            _ = dic[key]
            return True
        except KeyError:
            return False

    def concat_tuple(ouput_tuple):
        result = ""
        for m in ouput_tuple:
            result += str(m) + ' '

        return result

    def clear_directory(directory: str, log=DEFAULT_LOG):
        if not utils.os.path.isdir(directory):
            return log.error(f"Directory: {utils.os.path.join(utils.os.getcwd(), directory)} does not exist.")

        for filename in utils.os.listdir(directory):
            file_path = utils.os.path.join(directory, filename)

            try:
                if utils.os.path.isfile(file_path) or utils.os.path.islink(file_path):
                    utils.os.unlink(file_path)
                elif utils.os.path.isdir(file_path):
                    utils.shutil.rmtree(file_path)
            except Exception as e:
                log.error("Failed to delete %s. Reason: %s" % (file_path, e))

    def remove_files(files: list, log=DEFAULT_LOG):
        for file in files:
            if utils.os.path.exists(file):
                try:
                    utils.os.remove(file)
                except Exception as e:
                    log.error("Failed to delete %s. Reason %s" % (str(file), e))

    date_formatter = {
        "dd/mm/yyyy": "%d/%m/%Y",
        "dd-mm-yyyy": "%d-%m-%Y",
        "ddmmyyyy": "%d%m%Y",
        "mm/dd/yyyy": "%m/%d/%y",
        "mm dd, yyyy": "%B %d, %Y",
        "mm-dd-yyyy": "%b-%d-%Y",

        "dd/mm/yyyy hh:mm:ss": "%d/%m/%Y %H:%M:%S",
        "dd-mm-yyyy hh:mm:ss": "%d-%m-%Y %H:%M:%S",
        "dd-mm-yyyy hhmmss": "%d-%m-%Y %H%M%S",
        "dd-mm-yyyy hhmm": "%d-%m-%Y %H%M",
        "ddmmyyyy hhmmss": "%d%m%Y %H%M%S",
        "yyyymmdd-hhmmss": "%Y%m%d-%H%M%S",
    }

    def get_date_formatter(format_option, default_format_option):
        if utils.check_key_existence_in_dict(utils.date_formatter, format_option):
            return utils.date_formatter[format_option]
        else:
            return utils.date_formatter[default_format_option]

    def get_date_now(format_option: str = "dd-mm-yyyy"):
        date_format = utils.get_date_formatter(format_option, "dd-mm-yyyy")
        today = utils.date.today()
        return today.strftime(date_format)

    def get_datetime_now(format_option: str = "ddmmyyyy hhmmss"):
        datetime_format = utils.get_date_formatter(format_option, "ddmmyyyy hhmmss")
        now = utils.datetime.now()
        return now.strftime(datetime_format)
