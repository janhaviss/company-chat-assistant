import re
from enum import Enum
from typing import Any, Dict


# Session States
class SessionState(str, Enum):
    AWAITING_NAME = "AWAITING_NAME"
    AWAITING_EMAIL = "AWAITING_EMAIL"
    AWAITING_PHONE = "AWAITING_PHONE"
    READY = "READY"

    # Career / job application flow
    AWAITING_JOB_SELECTION = "AWAITING_JOB_SELECTION"
    AWAITING_RESUME = "AWAITING_RESUME"


# Validation Regex
EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

PHONE_RE = re.compile(
    r"^[6-9]\d{9}$"
)


CAREER_KEYWORDS = [
    "hiring",
    "hire",
    "job",
    "jobs",
    "job opening",
    "job openings",
    "job opportunity",
    "job opportunities",
    "vacancy",
    "vacancies",
    "career",
    "careers",
    "career opportunity",
    "career opportunities",
    "career opening",
    "career openings",
    "recruiting",
    "recruitment",
    "recruit",
    "open position",
    "open positions",
    "available position",
    "available positions",
    "available job",
    "available jobs",
    "job available",
    "jobs available",
    "work with your company",
    "work for your company",
    "join your company",
    "join the company",
]

JOB_APPLICATION_KEYWORDS = [
    "resume",
    "cv",
    "curriculum vitae",

    "job application",
    "job applications",

    "apply for a job",
    "apply for this job",
    "apply for the job",
    "apply for a position",
    "apply for this position",
    "apply for the position",

    "i want to apply",
    "i want to apply for",
    "want to apply",
    "want to apply for",

    "send my resume",
    "send my cv",

    "attach my resume",
    "attach my cv",

    "submit my resume",
    "submit my cv",

    "upload my resume",
    "upload my cv",

    "here is my resume",
    "here's my resume",
    "here is my cv",
    "here's my cv",

    "submit application",
    "submit my application",

    "apply now",
]


# Greeting / Farewell Detection
GREETING_WORDS = [
    "hi",
    "hii",
    "hello",
    "hey",
    "hiya",
    "yo",
    "good morning",
    "good afternoon",
    "good evening",
    "greetings",
]

FAREWELL_WORDS = [
    "bye",
    "goodbye",
    "bye bye",
    "see you",
    "see ya",
    "take care",
    "thank you bye",
    "thanks bye",
]


# In-memory Sessions
_sessions: Dict[str, Dict[str, Any]] = {}


# Create Session
def create_session(session_id: str) -> Dict[str, Any]:
    """
    Create a new chatbot session.

    Each user/session gets its own state so that the career
    application flow can continue across multiple messages.
    """

    session = {
        "state": SessionState.AWAITING_NAME,

        # Lead/contact information
        "lead_id": None,
        "name": None,
        "email": None,
        "phone": None,

        # Career information
        "selected_job": None,
    }

    _sessions[session_id] = session

    return session


# Get Session
def get_session(session_id: str) -> Dict[str, Any]:
    """
    Return an existing session.
    If the session does not exist, create it.
    """

    if session_id not in _sessions:
        return create_session(session_id)

    return _sessions[session_id]


# Email Validation
def is_valid_email(value: str) -> bool:
    """
    Validate an email address.
    """

    if not value:
        return False

    return bool(
        EMAIL_RE.match(value.strip())
    )


# Phone Validation
def is_valid_phone(value: str) -> bool:
    """
    Validate an 10-digit mobile number.
    """
    if not value:
        return False

    return bool(
        PHONE_RE.match(value.strip())
    )


# Text Normalization
def normalize_question(question: str) -> str:
    """
    Normalize user input before keyword matching.

    This:
    - converts to lowercase
    - removes extra whitespace
    - normalizes apostrophes
    """

    if not question:
        return ""

    question = question.lower().strip()

    # Normalize curly apostrophes
    question = question.replace("’", "'")

    # Collapse repeated whitespace
    question = re.sub(
        r"\s+",
        " ",
        question
    )

    return question


# Keyword Matching Helper
def contains_keyword(question: str, keyword: str) -> bool:
    """
    Check whether a keyword/phrase exists in the question.

    For normal words, word boundaries are used so that things like
    "hiring" don't accidentally match unrelated text.

    For multi-word phrases, the same boundary protection is used
    around the complete phrase.
    """

    if not question or not keyword:
        return False

    keyword = normalize_question(keyword)

    pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"

    return bool(
        re.search(pattern, question)
    )


# Greeting / Farewell Detection
def is_greeting(question: str) -> bool:
    """
    Detect a plain greeting ("hi", "hello", "good morning", ...).
    Checked before anything else in the pipeline — no KB lookup,
    no AI call.
    """

    q = normalize_question(question)

    if not q:
        return False

    return any(
        contains_keyword(q, word)
        for word in GREETING_WORDS
    )


def is_farewell(question: str) -> bool:
    """
    Detect a plain farewell ("bye", "goodbye", "take care", ...).
    """

    q = normalize_question(question)

    if not q:
        return False

    return any(
        contains_keyword(q, word)
        for word in FAREWELL_WORDS
    )


# Career Query Detection
def looks_like_career_query(question: str) -> bool:
    """
    Detect questions about hiring, careers, jobs, vacancies,
    recruitment, or available positions.

    Examples that return True:

        "Are you hiring?"
        "Do you have job openings?"
        "Any vacancies?"
        "What positions are available?"
        "Are there any jobs?"
        "Are you recruiting?"
        "What careers do you have?"
        "I want to work with your company"

    This function does NOT specifically mean that a resume
    should be uploaded.
    """

    q = normalize_question(question)

    if not q:
        return False

    return any(
        contains_keyword(q, keyword)
        for keyword in CAREER_KEYWORDS
    )


# Job Application Detection
def looks_like_job_application(question: str) -> bool:
    """
    Detect when the user is actually trying to apply for a job
    or submit/upload a resume or CV.

    Examples that return True:

        "I want to apply"
        "I want to apply for this job"
        "Here is my resume"
        "Can I send my CV?"
        "I want to submit my resume"
        "Attach my resume"
        "I want to apply for Backend Developer"

    These should normally lead to the resume/application flow.
    """

    q = normalize_question(question)

    if not q:
        return False

    return any(
        contains_keyword(q, keyword)
        for keyword in JOB_APPLICATION_KEYWORDS
    )


# Career Intent Classification
def get_career_intent(question: str):
    """
    Determine whether the message is:

        CAREER
        APPLICATION
        None

    APPLICATION gets priority because a message such as:

        "I want to apply for a job"

    contains both a career-related word ("job") and an
    application-related phrase ("apply for a job").

    Returns:
        "APPLICATION" -> actual application/resume request
        "CAREER"      -> hiring/job-opening enquiry
        None          -> unrelated
    """

    if looks_like_job_application(question):
        return "APPLICATION"

    if looks_like_career_query(question):
        return "CAREER"

    return None