import re
from enum import Enum
from typing import Any, Dict


class SessionState(str, Enum):
    AWAITING_NAME = "AWAITING_NAME"
    AWAITING_EMAIL = "AWAITING_EMAIL"
    AWAITING_PHONE = "AWAITING_PHONE"
    READY = "READY"
    AWAITING_JOB_SELECTION = "AWAITING_JOB_SELECTION"
    AWAITING_RESUME = "AWAITING_RESUME"


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[\d\s\-\+\(\)]{7,15}$")

JOB_APPLICATION_KEYWORDS = [
    "resume", "cv", "job application", "apply for a job", "apply for this job",
    "send my resume", "attach my resume", "submit my resume", "job opening",
]

_sessions: Dict[str, Dict[str, Any]] = {}


def create_session(session_id: str) -> Dict[str, Any]:
    session = {
        "state": SessionState.AWAITING_NAME,
        "lead_id": None,
        "name": None,
        "email": None,
        "phone": None,
        "selected_job": None,
    }
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _sessions:
        return create_session(session_id)
    return _sessions[session_id]


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip()))


def is_valid_phone(value: str) -> bool:
    return bool(PHONE_RE.match(value.strip()))


def looks_like_job_application(question: str) -> bool:
    q = question.lower()
    return any(keyword in q for keyword in JOB_APPLICATION_KEYWORDS)