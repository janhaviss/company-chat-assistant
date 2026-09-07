import asyncio
import os
import uuid
from typing import Dict, List, Optional

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    UploadFile, File, Form, HTTPException
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from knowledge_base import KNOWLEDGE_BASE
from matchers import find_intent
from ai_service import ask_ai

from session_manager import (
    get_session, is_valid_email, is_valid_phone,
    looks_like_job_application, SessionState,
)
from db import init_db, save_lead, save_application, get_lead_by_session
from email_service import send_new_application_email, send_new_lead_email, send_unanswered_question_email
from jobs import get_open_jobs, format_job_listing, match_job_selection


app = FastAPI(
    title="Company AI Assistant",
    description=(
        "Hybrid company assistant using knowledge base, "
        "intent matching, AI fallback, and job-applicant intake"
    ),
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Configuration
KB_CONFIDENCE_THRESHOLD = 0.70

UPLOAD_DIR = "uploads/resumes"
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
MAX_RESUME_SIZE_MB = 5

os.makedirs(UPLOAD_DIR, exist_ok=True)

active_connections: Dict[str, WebSocket] = {}


@app.on_event("startup")
def on_startup():
    init_db()


# Request / Response Models
class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    question: str
    intent: Optional[str]
    confidence: float
    matched_keywords: List[str]
    answer: str
    source: str
    needs_contact: bool = False


class MenuOption(BaseModel):
    question_id: str
    question: str


class ContactRequest(BaseModel):
    email: EmailStr
    question: str

@app.get("/")
def root():
    return {"message": "Company AI Assistant is running.", "docs": "/docs"}


@app.get("/menu", response_model=List[MenuOption])
def get_menu():
    menu = []
    for intent, data in KNOWLEDGE_BASE.items():
        menu.append({"question_id": intent, "question": data["questions"][0]})
    return menu


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Legacy stateless endpoint — kept as-is for any integration still
    using plain request/response. The widget should migrate to the
    /ws/{session_id} WebSocket endpoint below, which adds lead capture
    and the job-applicant flow on top of this same logic.
    """
    question = request.question.strip()

    if not question:
        return {
            "question": question, "intent": None, "confidence": 0.0,
            "matched_keywords": [], "answer": "Please enter a question.",
            "source": "validation", "needs_contact": False,
        }

    result = find_intent(question)
    intent = result.get("intent")
    confidence = result.get("confidence", 0.0)
    matched_keywords = result.get("matched_keywords", [])
    answer = result.get("answer")

    if intent is not None and confidence >= KB_CONFIDENCE_THRESHOLD and answer:
        return {
            "question": question, "intent": intent, "confidence": confidence,
            "matched_keywords": matched_keywords, "answer": answer,
            "source": "knowledge_base", "needs_contact": False,
        }

    ai_answer = ask_ai(question)

    if ai_answer == "CONTACT_TEAM":
        return {
            "question": question, "intent": "contact_team", "confidence": confidence,
            "matched_keywords": matched_keywords,
            "answer": (
                "I don't have enough information to answer that accurately. "
                "Please provide your email so our team can get back to you."
            ),
            "source": "contact_team", "needs_contact": True,
        }

    return {
        "question": question, "intent": "ai_fallback", "confidence": confidence,
        "matched_keywords": matched_keywords, "answer": ai_answer,
        "source": "ai", "needs_contact": False,
    }


@app.post("/contact")
def contact_team(request: ContactRequest):
    print("New enquiry received")
    print("Email:", request.email)
    print("Question:", request.question)
    return {"message": "Thank you. Our team will get back to you at the provided email address."}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket
    session = get_session(session_id)

    if session["state"] == SessionState.AWAITING_NAME:
        await websocket.send_json({
            "sender": "bot",
            "text": "Hi! Before we get started, what's your name?",
            "stage": session["state"],
        })

    try:
        while True:
            data = await websocket.receive_json()
            user_text = (data.get("text") or "").strip()
            reply = await handle_message(session_id, session, user_text)
            await websocket.send_json(reply)
    except WebSocketDisconnect:
        active_connections.pop(session_id, None)


async def handle_message(session_id: str, session: dict, user_text: str) -> dict:
    """
    Thin wrapper around _resolve_reply that stamps every outgoing message
    with the session's current stage (its state machine value) — e.g.
    "AWAITING_EMAIL", "READY", "AWAITING_RESUME". The frontend uses this to
    know when lead capture has finished and normal Q&A has started, instead
    of guessing from message count or text content.
    """
    reply = await _resolve_reply(session_id, session, user_text)
    reply["stage"] = session["state"]
    return reply


async def _resolve_reply(session_id: str, session: dict, user_text: str) -> dict:
    state = session["state"]

    if not user_text:
        return {"sender": "bot", "text": "Please type something."}

    if state == SessionState.AWAITING_NAME:
        session["name"] = user_text
        session["state"] = SessionState.AWAITING_EMAIL
        return {"sender": "bot", "text": "Thanks! What's your email address?"}

    if state == SessionState.AWAITING_EMAIL:
        if not is_valid_email(user_text):
            return {"sender": "bot", "text": "That doesn't look like a valid email — could you try again?"}
        session["email"] = user_text
        session["state"] = SessionState.AWAITING_PHONE
        return {"sender": "bot", "text": "Great, and your phone number?"}

    if state == SessionState.AWAITING_PHONE:
        if not is_valid_phone(user_text):
            return {"sender": "bot", "text": "That doesn't look like a valid phone number — could you try again?"}
        session["phone"] = user_text
        lead_id = save_lead(session_id, session["name"], session["email"], session["phone"])
        session["lead_id"] = lead_id
        session["state"] = SessionState.READY
        asyncio.create_task(
            asyncio.to_thread(
                send_new_lead_email, session["name"], session["email"], session["phone"]
            )
        )

        return {"sender": "bot", "text": f"Thanks {session['name']}! How can I help you today?"}

    if state == SessionState.AWAITING_RESUME:
        return {
            "sender": "bot",
            "text": (
                "I still need your resume attached before I can submit your "
                "application — please use the attachment button to upload it "
                "(PDF or Word doc)."
            ),
            "needs_resume": True,
        }

    if state == SessionState.AWAITING_JOB_SELECTION:
        open_jobs = get_open_jobs()
        job = match_job_selection(user_text, open_jobs)

        if job is None:
            return {
                "sender": "bot",
                "text": (
                    "I didn't catch which role you meant — here are the current "
                    f"openings again:\n\n{format_job_listing(open_jobs)}\n\n"
                    "You can type the role name or its number."
                ),
                "job_options": [j["title"] for j in open_jobs],
            }

        session["selected_job"] = job
        session["state"] = SessionState.AWAITING_RESUME
        return {
            "sender": "bot",
            "text": f"Great choice! Please attach your resume (PDF or Word doc) to apply for {job['title']}.",
            "needs_resume": True,
        }

    # ---- Run the existing matcher once ----
    result = find_intent(user_text)
    intent = result.get("intent")
    confidence = result.get("confidence", 0.0)
    answer = result.get("answer")
    intent_is_job_related = intent is not None and any(
        term in intent.lower() for term in ("job", "career", "apply", "resume", "cv")
    )

    if intent_is_job_related or looks_like_job_application(user_text):
        open_jobs = get_open_jobs()

        if not open_jobs:
            # No openings right now — never ask for a resume with nothing
            # to apply to. Stays in normal Q&A.
            return {
                "sender": "bot",
                "text": (
                    "We don't have any open positions right now, but feel free "
                    "to check back later — I'm happy to help with anything else "
                    "in the meantime!"
                ),
            }

        session["state"] = SessionState.AWAITING_JOB_SELECTION
        return {
            "sender": "bot",
            "text": (
                f"Here are our current openings:\n\n{format_job_listing(open_jobs)}\n\n"
                "Which role are you interested in? Type the role name or tap one below."
            ),
            "job_options": [j["title"] for j in open_jobs],
        }

    if intent is not None and confidence >= KB_CONFIDENCE_THRESHOLD and answer:
        return {"sender": "bot", "text": answer}
    ai_answer = await asyncio.to_thread(ask_ai, user_text)

    if ai_answer == "CONTACT_TEAM":
        lead = get_lead_by_session(session_id)
        if lead is not None:
            asyncio.create_task(
                asyncio.to_thread(
                    send_unanswered_question_email,
                    lead["name"], lead["email"], lead["phone"], user_text,
                )
            )
        return {
            "sender": "bot",
            "text": (
                "I don't have enough information to answer that accurately. "
                "Our team will follow up with you by email."
            ),
        }

    if ai_answer == "NOT_RELEVANT":
        return {
            "sender": "bot",
            "text": (
                "I'm not quite sure what you mean — could you tell me more, "
                "or ask about our services, products, or careers?"
            ),
        }

    return {"sender": "bot", "text": ai_answer}


# Resume upload
@app.post("/api/upload-resume")
async def upload_resume(session_id: str = Form(...), file: UploadFile = File(...)):
    session = get_session(session_id)

    if session["state"] != SessionState.AWAITING_RESUME:
        raise HTTPException(
            status_code=400,
            detail="No pending job application for this session.",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOC, or DOCX files are accepted.")

    contents = await file.read()
    if len(contents) > MAX_RESUME_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File must be under {MAX_RESUME_SIZE_MB}MB.")

    safe_filename = f"{session_id}_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    lead = get_lead_by_session(session_id)
    if lead is None:
        raise HTTPException(status_code=400, detail="No lead found for this session.")

    job_title = (session.get("selected_job") or {}).get("title", "General Application")

    save_application(lead["id"], file_path, file.filename, job_title)

    send_new_application_email(
        name=lead["name"],
        email=lead["email"],
        phone=lead["phone"],
        resume_path=file_path,
        original_filename=file.filename,
        job_title=job_title,
    )

    session["state"] = SessionState.READY
    session["selected_job"] = None

    confirmation = {
        "sender": "bot",
        "text": "Got your resume — thanks! Our hiring team will review it and be in touch.",
        "stage": session["state"],
    }

    ws = active_connections.get(session_id)
    if ws is not None:
        await ws.send_json(confirmation)

    return {"message": "Resume received.", "confirmation": confirmation}