from typing import Any

attribute_templates = [
    ["days_in_view", list],
    ["web_elements_in_view", dict],
    ["times_in_view", list],

    ["available_sessions", dict],

    ["reserved_sessions", dict],
    ["booked_sessions", dict],
    ["lesson_name", str],

    ["earlier_sessions", dict],
    ["cached_earlier_sessions", dict],
]


class Types:
    SIMULATOR = "simulator"
    PRACTICAL = "practical"
    BTT = "btt"
    RTT = "rtt"
    FTT = "ftt"
    PT = "pt"


field_types = [attr for attr in dir(Types) if not callable(getattr(Types, attr)) and not attr.startswith("__")]


class CDCAbstract:
    def __init__(self, username, password, headless=False):
        self.username = username
        self.password = password
        self.headless = headless

        for field_type in field_types:
            field_type_str = getattr(Types, field_type)
            for attribute_template in attribute_templates:
                setattr(self, f"{attribute_template[0]}_{field_type_str}", attribute_template[1]())

        # Simulator
        self.can_book_next_simulator = True
        self.has_auto_reserved_simulator = False

        # Practical
        self.can_book_next_practical = True
        self.has_auto_reserved_practical = False

        # PT
        self.can_book_next_pt = True

    def __str__(self):
        blacklist_attr_names = "captcha_solver,"
        abstract_str = "# ------------------------------------- - ------------------------------------ #\n"
        abstract_str += "CDC_ABSTRACT\n"

        abstract_str += f"user = ######\n"  # {str(self.username)}\n"
        abstract_str += f"password = ######\n"  # {str(self.password)}\n"
        abstract_str += f"headless = {str(self.headless)}\n"

        abstract_str += "\n"

        abstract_attr = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        for field_type in field_types:
            abstract_str += f"# {str(field_type)}\n"

            field_type_str = getattr(Types, field_type)
            for attr in abstract_attr:
                if (field_type_str in attr) and (attr not in blacklist_attr_names):
                    abstract_str += f"# {str(attr)} = {str(getattr(self, attr))}\n"
            abstract_str += "\n"
        abstract_str += "# ------------------------------------- - ------------------------------------ #"

        return abstract_str

    def reset_attributes_for_all_fieldtypes(self):
        for field_type in field_types:
            self.reset_attributes_with_fieldtype(getattr(Types, field_type))

    def reset_attributes_with_fieldtype(self, field_type: str):
        whitelisted_attributes = ["cached_earlier_sessions"]
        for attribute_template in attribute_templates:
            attribute = attribute_template[0]
            if attribute not in whitelisted_attributes:
                self.set_attribute_with_fieldtype(attribute, field_type, attribute_template[1]())

        if field_type == Types.SIMULATOR:
            self.can_book_next_simulator = True
            self.has_auto_reserved_simulator = False

        if field_type == Types.PRACTICAL:
            self.can_book_next_practical = True
            self.has_auto_reserved_practical = False

        if field_type == Types.PT:
            self.can_book_next_pt = True

    def get_attribute(self, attribute: str):
        return getattr(self, attribute)

    def set_attribute(self, attribute: str, value: Any):
        setattr(self, attribute, value)

    def get_attribute_with_fieldtype(self, attribute: str, field_type: str):
        return getattr(self, f"{attribute}_{field_type}")

    def set_attribute_with_fieldtype(self, attribute: str, field_type: str, value: Any):
        setattr(self, f"{attribute}_{field_type}", value)
