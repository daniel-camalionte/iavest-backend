from email.mime.text import MIMEText

import config.env as memory
import smtplib

class SMTP:
    """ SMTP
    """
    def __init__(self):
        self.host = memory.smtp["HOST"]
        self.port = memory.smtp["PORT"]
        self.msgFrom = memory.smtp["FROM"]
        self.pwd = memory.smtp["PASS"]
        
    def send(self, msgTo, title, body):
        """ send
        """
        try:
            smtpObj = smtplib.SMTP_SSL(self.host, self.port)
            msgFrom = self.msgFrom
            toPass = self.pwd
            smtpObj.login(msgFrom, toPass)

            msg = MIMEText(body, 'html')
            msg['Subject'] = title
            msg['From'] = msgFrom
            msg['To'] = msgTo

            smtpObj.sendmail(msgFrom, msgTo, msg.as_string())
            smtpObj.quit()
            return 1
        except Exception as e:
            print(f"SMTP Error: {str(e)}")
            return 0