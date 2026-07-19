import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


GOOGLE_PASSWORD = os.getenv("GOOGLEPASSWORD")
EMAIL = os.getenv("MAIN_MAIL")

def send_verification_email(email, system_name):
    code = random.randint(100000, 999999)
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(EMAIL, GOOGLE_PASSWORD)

        msg = MIMEMultipart()
        msg['From'] = f"{system_name} <{EMAIL}>"
        msg['To'] = email
        msg['Subject'] = system_name + " - 본인 인증 확인 메일"

            
        msg.attach(MIMEText(
            f"""<html>
                <body>
                    <h1>본인 확인 이메일</h1>
                    <p>당신이 맞음을 인증하고 싶으시다면 아래 인증 코드를 입력해주세요.</p>
                    <h2>인증 코드: {code}</h2>
                    <p>감사합니다.</p>
                </body>
            </html>""", 'html'))

        smtp.send_message(msg)

        return code

    return None 