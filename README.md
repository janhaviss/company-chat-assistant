# Company AI Assistant

A real-time AI chatbot for a company website using **FastAPI (WebSockets), React, keyword/intent matching, a company knowledge base, OpenRouter AI fallback, SQLite, and email notifications**.

## Features

- **Real-time chat** over a WebSocket connection (`/ws/{session_id}`), not per-message HTTP calls
- **Mandatory lead capture** — every visitor is asked for name, email, and phone before anything else, saved to SQLite
- Answers common company questions from a knowledge base (keyword/intent matching, confidence-based)
- **AI fallback** (OpenRouter) for questions the knowledge base doesn't cover, which itself triages into three outcomes:
  - a direct answer
  - `CONTACT_TEAM` — a genuine question the AI can't answer from company info → emails the team the visitor's details and the question
  - `NOT_RELEVANT` — gibberish, spam, or off-topic input → gently redirected, no email sent
- **Job-application flow**, gated on actual open roles:
  - Career-related intent lists current openings from `jobs.py`
  - If there are none, the bot says so and never asks for a resume
  - If the visitor picks a role (by tapping an option or typing it), resume upload becomes mandatory for that specific role
  - Resume upload (`POST /api/upload-resume`) validates file type/size, stores the file, and emails the hiring manager with the applicant's details, the role, and the resume attached
- **Email notifications** (Gmail SMTP) for three distinct events: new lead, new job application, and unanswered-but-genuine question — kept separate so the inbox stays meaningful
- Suggested questions through the `/menu` endpoint
- React-based chat interface with tappable job-option buttons and a resume-attachment control that only appears when needed

## Tech Stack

- **Frontend:** React (WebSocket client + REST for menu/upload)
- **Backend:** FastAPI (WebSocket + REST), Python
- **AI:** OpenRouter (via OpenAI SDK)
- **Storage:** SQLite (`chatbot.db` — no separate DB server needed)
- **Email:** Gmail SMTP (App Password)
- **Data:** Python-based knowledge base + job openings list

## How It Works

```text
Browser opens WebSocket (/ws/{session_id})
      ↓
Lead capture gate: name → email → phone → saved to SQLite
      ↓ (email: "new lead" sent)
Visitor's message
      ↓
Career-related intent?
   ↙            ↘
 Yes             No
  ↓               ↓
Any open      Intent / Keyword Matcher
roles?               ↓
 ↙    ↘        High confidence?
No    Yes        ↙        ↘
 ↓     ↓        Yes        No
"No   List            ↓     ↓
open  roles,      Knowledge  AI fallback
roles" ask which     Base       ↓
        one              Answer / CONTACT_TEAM / NOT_RELEVANT
        ↓                        ↓            ↓
   Resume required          (emails team   (no email,
   for that role             + question)   gentle redirect)
        ↓
   Upload → validated, saved, emailed to hiring manager
```

Common questions are still answered directly from the knowledge base with no AI call involved — the AI is only invoked when nothing matches confidently.

## Project Structure

```text
backend/
├── main.py              # FastAPI app: WebSocket chat, REST endpoints, orchestration
├── matchers.py           # Keyword/intent scoring against the knowledge base
├── knowledge_base.py      # Company Q&A content (intents, keywords, answers)
├── ai_service.py          # OpenRouter fallback + CONTACT_TEAM / NOT_RELEVANT triage
├── session_manager.py     # Per-session state machine (lead capture → job flow)
├── jobs.py                # Current job openings + role-matching helpers
├── db.py                  # SQLite setup, leads & applications tables
├── email_service.py       # Gmail SMTP notifications (lead / application / question)
├── requirements.txt
└── .env

uploads/
└── resumes/               # Uploaded resume files land here

chatbot.db                 # SQLite database file (auto-created on first run)

frontend/
└── React application (App.jsx — WebSocket client, job options, resume attach)
```

## Setup

### Backend

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install python-multipart --break-system-packages
```

`python-multipart` is required for the resume upload endpoint — FastAPI won't error until that route is actually hit, so it's easy to miss.

Create `.env`:

```env
OPENROUTER_API_KEY=your_api_key_here

# Email notifications (Gmail SMTP)
GMAIL_ADDRESS=youraccount@gmail.com
GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx
HIRING_MANAGER_EMAIL=manager@yourcompany.com
```

`GMAIL_APP_PASSWORD` is a 16-character App Password (not your normal Gmail password) — generate one at https://myaccount.google.com/apppasswords (requires 2-Step Verification enabled on that Gmail account). If the three email variables aren't set, the app still runs fine — it just logs "email not configured" and skips sending, so you can develop without email set up first.

Run the FastAPI server:

```bash
uvicorn main:app --reload
```

No database setup step is needed — `chatbot.db` (SQLite) is created automatically on startup, in whichever directory you run `uvicorn` from. To inspect it: `sqlite3 chatbot.db` or open it with [DB Browser for SQLite](https://sqlitebrowser.org/).

API documentation:

```text
http://127.0.0.1:8000/docs
```

(Note: `/docs` doesn't render the WebSocket endpoint interactively — test `/ws/{session_id}` from the frontend or a WebSocket client instead.)

### Frontend

```bash
npm install
npm run dev
```

The React development server normally runs at:

```text
http://localhost:5173
```

## API Endpoints

### `GET /`
Checks that the backend is running.

### `GET /menu`
Returns suggested questions for the chatbot.

### `WS /ws/{session_id}`
**Primary chat endpoint.** Real-time, stateful per session. Handles lead capture, KB/AI answers, and the full job-application flow. Client sends `{"text": "..."}`; server sends `{"sender": "bot", "text": "...", "stage": "...", "needs_resume": bool, "job_options": [...]}` (the last three fields only appear when relevant).

### `POST /api/upload-resume`
`multipart/form-data` with `session_id` and `file` (PDF/DOC/DOCX, ≤5MB). Only accepted while that session is in the `AWAITING_RESUME` stage. Saves the file, records the application (linked to the role picked), and emails the hiring manager.

### `POST /chat` *(legacy)*
Original stateless endpoint, kept for backward compatibility. Does not include lead capture or the job-application flow — new integrations should use the WebSocket endpoint instead.

### `POST /contact` *(legacy)*
Original standalone contact-capture endpoint. No longer called by the current frontend (lead info is now captured upfront by the WebSocket flow instead), but left in place in case anything else still depends on it.

## Environment Variables

Never commit your API key or email credentials to GitHub.

Add this to `.gitignore`:

```gitignore
.env
venv/
__pycache__/
node_modules/
chatbot.db
uploads/
```

## Known Limitations

- **Sessions are in-memory** (`session_manager.py`). Fine for a single process; if you run multiple uvicorn/gunicorn workers in production, move session state to Redis so all workers share it.
- **File type validation is extension-based**, not content-based. Add `python-magic` to check actual file signatures if you want to guard against a renamed malicious file.
- **No rate limiting or dedup** on the unanswered-question email — a visitor asking several unanswerable questions in one session triggers one email each.
- **`NOT_RELEVANT`/`CONTACT_TEAM` classification depends on the LLM following an exact-output instruction.** `openrouter/free` can be inconsistent here — worth spot-checking against edge cases and upgrading the model for this call if misclassifications show up.

## Current Scope

The assistant answers company website questions from verified company information, using AI only when the keyword/intent matcher can't confidently answer. On top of that, it captures every visitor as a lead, guides genuine job seekers through picking a real open role before requesting a resume, and routes anything the AI can't resolve to a human — while filtering out spam and gibberish so that only real inquiries reach an inbox.
