import requests

from src.utils.log import Log


class TelegramBot:
    def __init__(self, token: str, default_chat_id: int, log: Log):
        self.token = token
        self.default_chat_id = default_chat_id
        self.log = log

    def send_msg(self, msg_subject: str, msg_body: str, chat_id: int = None):
        chat_id = str(chat_id or self.default_chat_id)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage" \
              f"?chat_id={chat_id}&text=<b>{msg_subject}</b>\n{msg_body}&parse_mode=HTML"
        return requests.get(url)
