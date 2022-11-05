from src.utils.notifications.mail import Mail
from src.utils.notifications.telegram_bot import TelegramBot


class NotificationManager:
    def __init__(self, log, mail_config: dict = None, telegram_config: dict = None):
        self.mail_server = False
        self.telegram_bot = False

        if mail_config and mail_config["email_notification_enabled"]:
            self.mail_server = Mail(
                smtp_server=mail_config["smtp_server"],
                smtp_server_port=mail_config["smtp_port"],
                smtp_username=mail_config["smtp_user"],
                smtp_user_password=mail_config["smtp_pw"],
                log=log
            )
            self.mail_server.set_default_recipient(mail_config["recipient_address"])

        if telegram_config and telegram_config["telegram_notification_enabled"]:
            self.telegram_bot = TelegramBot(
                token=telegram_config["telegram_bot_token"],
                default_chat_id=telegram_config["telegram_chat_id"],
                log=log
            )

    def send_notification_all(self, title: str, msg: str):
        result_tele, result_mail = None, None

        if self.telegram_bot:
            result_tele = self.telegram_bot.send_msg(msg_subject=title, msg_body=msg)

        if self.mail_server:
            result_mail = self.mail_server.send_mail(mail_subject=title, mail_body=msg)

        return result_tele, result_mail

    def send_notification_telegram(self, title: str, msg: str):
        if self.telegram_bot:
            return self.telegram_bot.send_msg(msg_subject=title, msg_body=msg)

    def send_notification_mail(self, title: str, msg: str):
        if self.mail_server:
            return self.mail_server.send_mail(mail_subject=title, mail_body=msg)
