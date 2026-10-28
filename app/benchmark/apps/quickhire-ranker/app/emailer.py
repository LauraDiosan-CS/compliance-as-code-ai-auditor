import smtplib
from email.message import EmailMessage

SENDER = "jobs@quickhire.example"

TEMPLATE = """Dear applicant,

Thank you for your interest in this position. After careful consideration we have decided not to
move forward with your application.

Kind regards,
The Hiring Team
"""


def send_rejection_email(to, job_id):
    msg = EmailMessage()
    msg["From"], msg["To"] = SENDER, to
    msg["Subject"] = f"Your application (job {job_id})"
    msg.set_content(TEMPLATE)
    with smtplib.SMTP("smtp.quickhire.example", 25) as s:
        s.send_message(msg)
