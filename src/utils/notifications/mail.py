import smtplib
import socket
from email.message import EmailMessage

from src.utils.log import Log


class NoMailServer(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class Mail:
    def __init__(self, smtp_server: str, smtp_server_port: int, smtp_username: str, smtp_user_password: str, log: Log):
        try:
            mail_server = smtplib.SMTP(smtp_server, smtp_server_port)
            mail_server.ehlo()
            mail_server.starttls()
            mail_server.login(smtp_username, smtp_user_password)
        except socket.error as e:
            log.error(f"Could not connect to mail server: {str(e)}")
            mail_server = None
        except Exception as e:
            log.error(f"Something when wrong while connecting to mail server: {str(e)}")
            mail_server = None

        self.server = mail_server
        self.log = log
        self.sender = smtp_username
        self.default_recipient = self.sender

    def send_mail(self, mail_subject: str, mail_body, receiver: str = None):
        mail_success = False
        try:
            msg = EmailMessage()
            msg.set_content(mail_body)
            msg["From"] = self.sender
            msg["To"] = receiver or self.default_recipient
            msg["Subject"] = mail_subject

            if self.server:
                self.server.sendmail(
                    from_addr=self.sender,
                    to_addrs=receiver or self.default_recipient,
                    msg=msg.as_string()
                )
            else:
                raise NoMailServer
        except NoMailServer:
            self.log.error("No mail server was found. Please check previous logs for further details.")
        except socket.gaierror:
            self.log.error("Socket issue while sending email - Are you in VPN/proxy?")
        except Exception as e:
            self.log.error(f"Something went wrong while sending an email: {e}")
        else:
            mail_success = True
        finally:
            return mail_success

    def set_default_recipient(self, recipient: str):
        self.default_recipient = recipient
