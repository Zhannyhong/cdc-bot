import logging
import os
import sys

from src.utils.common import utils

FORMATTER = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
DEFAULT_CONFIG = {
    "log_level": 1,  # 1 - DEBUG, 2 - INFO, 3 - WARN, 4- ERROR
    "print_log_to_output": True,
    "write_log_to_file": True,
    "clear_logs_init": False,
    "appends_stack_call_to_log": True,
    "save_solved_captchas": False
}


class Log:

    def __init__(self, directory: str, name: str = "cdc-helper", config: dict = DEFAULT_CONFIG):
        log = logging.getLogger(name)

        self.logger = log
        self.name = name
        self.directory = directory
        self.config = utils.init_config_with_default(config, DEFAULT_CONFIG)

        if not os.path.exists(directory):
            os.makedirs(directory)

        if self.config["clear_logs_init"]:
            utils.clear_directory(directory=self.directory, log=self.logger)

        if self.config["print_log_to_output"]:
            terminal_output = logging.StreamHandler(sys.stdout)
            terminal_output.setFormatter(FORMATTER)
            log.addHandler(terminal_output)

        if self.config["write_log_to_file"]:
            file_output = logging.FileHandler(
                os.path.join(directory, f"tracker_{utils.get_datetime_now('yyyymmdd-hhmmss')}.log"))
            file_output.setFormatter(FORMATTER)
            log.addHandler(file_output)

        if self.config["save_solved_captchas"]:
            if not os.path.exists("solved_captchas"):
                os.makedirs("solved_captchas")

        log.setLevel(int(self.config["log_level"]) * 10)

    def append_stack_if(self, log_type, *output):
        msg = utils.concat_tuple(output)
        if self.config["appends_stack_call_to_log"]:
            log_type("=======================================================================================")
            log_type(*output, stack_info=True)
            log_type("\n=======================================================================================\n")
        else:
            log_type(msg)

    def info(self, *output):
        self.append_stack_if(self.logger.info, *output)

    def debug(self, *output):
        self.append_stack_if(self.logger.debug, *output)

    def error(self, *output):
        self.append_stack_if(self.logger.error, *output)

    def warning(self, *output):
        self.append_stack_if(self.logger.warning, *output)

    def info_if(self, condition: bool, *output):
        if condition:
            self.info(*output)

    def debug_if(self, condition: bool, *output):
        if condition:
            self.debug(*output)

    def error_if(self, condition: bool, *output):
        if condition:
            self.error(*output)

    def warning_if(self, condition: bool, *output):
        if condition:
            self.warning(*output)
