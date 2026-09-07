from typing import Optional

# Current job openings
# Edit this list as roles open and close — set "open": False (or just
# remove the entry) for a role once it's filled.
#
# "keywords" are optional extra phrases that count as selecting this
# role when the user types freely instead of tapping an option.

JOB_OPENINGS = [
    {
        "id": "backend-developer",
        "title": "Backend Developer",
        "keywords": ["backend", "python developer", "fastapi developer", "api developer"],
        "open": True,
    },
    {
        "id": "frontend-developer",
        "title": "Frontend Developer",
        "keywords": ["frontend", "react developer", "ui developer"],
        "open": True,
    },
    {
        "id": "ai-ml-engineer",
        "title": "AI/ML Engineer",
        "keywords": ["ai engineer", "ml engineer", "machine learning engineer"],
        "open": True,
    },
]


def get_open_jobs() -> list[dict]:
    return [job for job in JOB_OPENINGS if job.get("open")]


def format_job_listing(jobs: list[dict]) -> str:
    return "\n".join(f"{i + 1}. {job['title']}" for i, job in enumerate(jobs))


def match_job_selection(user_text: str, jobs: list[dict]) -> Optional[dict]:
    """
    Match a user's free-text (or tapped-option) reply to one of the
    listed jobs — by number ("2"), exact/partial title match, or one
    of the job's extra keywords.
    """
    text = user_text.strip().lower()

    # Numbered selection, e.g. "2" or "option 2"
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits.isdigit() and digits:
        index = int(digits) - 1
        if 0 <= index < len(jobs):
            return jobs[index]

    # Title or keyword match
    for job in jobs:
        if job["title"].lower() in text:
            return job
        for keyword in job.get("keywords", []):
            if keyword.lower() in text:
                return job

    return None