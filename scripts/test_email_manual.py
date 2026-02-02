
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

smtp_host = os.getenv('SMTP_HOST')
smtp_port = int(os.getenv('SMTP_PORT', 587))
smtp_user = os.getenv('SMTP_USER')
smtp_password = os.getenv('SMTP_PASSWORD')
recipients = os.getenv('EMAIL_RECIPIENTS', '').split(',')

print(f"Testing SMTP: {smtp_host}:{smtp_port}")
print(f"User: {smtp_user}")
print(f"Recipients: {recipients}")

try:
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.set_debuglevel(1)
        server.starttls()
        server.login(smtp_user, smtp_password)
        
        msg = MIMEText("This is a test email from the manual script.")
        msg['Subject'] = "Manual SMTP Test"
        msg['From'] = smtp_user
        msg['To'] = ", ".join(recipients)
        
        server.send_message(msg)
        print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
