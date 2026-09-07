import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

# GMAIL_ADDRESS: the Gmail account sending the notification
# GMAIL_APP_PASSWORD: a 16-character App Password — generated at https://myaccount.google.com/apppasswords
# HIRING_MANAGER_EMAIL: where the notification should be sent

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
HIRING_MANAGER_EMAIL = os.environ.get("HIRING_MANAGER_EMAIL")


def _send_email(subject: str, body: str, attachment: tuple[bytes, str] | None = None) -> None:
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD and HIRING_MANAGER_EMAIL):
        print(
            "[email_service] Email not configured — skipping send. "
            "Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, HIRING_MANAGER_EMAIL."
        )
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = HIRING_MANAGER_EMAIL
    msg.set_content(body)

    if attachment is not None:
        data, filename = attachment
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=filename,
        )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
    except smtplib.SMTPException as exc:
        print(f"[email_service] Failed to send notification email: {exc}")


def send_new_application_email(
    name: str,
    email: str,
    phone: str,
    resume_path: str,
    original_filename: str,
    job_title: str,
) -> None:
    with open(Path(resume_path), "rb") as f:
        data = f.read()

    _send_email(
        subject=f"New job application: {name} — {job_title}",
        body=(
            "A new job application was submitted via the chatbot.\n\n"
            f"Role applied for: {job_title}\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n\n"
            "Resume is attached."
        ),
        attachment=(data, original_filename),
    )


def send_new_lead_email(name: str, email: str, phone: str) -> None:
    """
    Fired right after lead capture completes, for every visitor —
    regardless of what they go on to ask about (contact, custom
    software, demo request, etc.). Job applications get their own,
    separate email (send_new_application_email) once a resume is
    attached, so a job applicant will trigger two emails total.
    """
    _send_email(
        subject=f"New chatbot lead: {name}",
        body=(
            "A new visitor completed the chatbot's intake form.\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n"
        ),
    )


def send_unanswered_question_email(name: str, email: str, phone: str, question: str) -> None:
    """
    Fired when ask_ai() returns CONTACT_TEAM — a genuine, on-topic
    question the knowledge base and AI fallback couldn't answer.
    Deliberately NOT fired for NOT_RELEVANT (gibberish/spam), so this
    inbox only fills up with things actually worth a human's time.
    """
    _send_email(
        subject=f"Chatbot: unanswered question from {name}",
        body=(
            "A visitor asked something the chatbot couldn't answer from "
            "its knowledge base.\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n\n"
            f"Question: {question}\n"
        ),
    )