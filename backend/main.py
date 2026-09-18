import os
import re
import uuid
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schemas import ChatMessageIn, ChatMessageOut, HealthOut
from config import settings
from services.ai_client import generate_reply

app = FastAPI(title="MPA Web Chatbot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

SESSIONS: dict = {}

LEAD_WEBHOOK_URL = os.getenv("LEAD_WEBHOOK_URL", "").strip()

LEAD_PATTERN = re.compile(
    r"##LEAD##\s*\n"
    r"\s*name\s*:\s*(?P<name>[^\n]+)\n"
    r"\s*phone\s*:\s*(?P<phone>[^\n]+)\n"
    r"\s*service\s*:\s*(?P<service>[^\n]+)",
    re.IGNORECASE,
)


def extract_lead(text: str):
    m = LEAD_PATTERN.search(text)
    if not m:
        return None
    return {
        "name": m.group("name").strip(),
        "phone": m.group("phone").strip(),
        "service": m.group("service").strip(),
    }


def strip_lead_block(text: str) -> str:
    return re.sub(r"##LEAD##.*$", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


async def send_lead_to_sheets(lead: dict, session_id: str) -> None:
    if not LEAD_WEBHOOK_URL:
        print("[LEAD] No LEAD_WEBHOOK_URL set — lead was NOT saved.")
        return
    payload = {
        "session_id": session_id,
        "name": lead["name"],
        "phone": lead["phone"],
        "service": lead["service"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(LEAD_WEBHOOK_URL, json=payload)
            print(f"[LEAD] Saved to Google Sheet → {r.status_code}")
    except Exception as e:
        print(f"[LEAD] Webhook failed: {e}")


@app.get("/")
async def root():
    return {"status": "MPA Chatbot API", "version": "1.0.0", "model": settings.OPENAI_MODEL}


@app.get("/health", response_model=HealthOut)
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            )
        reachable = r.status_code < 500
    except Exception:
        reachable = False
    return HealthOut(status="ok", openai_reachable=reachable)


@app.post("/api/chat", response_model=ChatMessageOut)
async def chat(payload: ChatMessageIn):
    session_id = payload.session_id.strip() or str(uuid.uuid4())

    history = SESSIONS.get(session_id, [])
    history.append({
        "role": "user",
        "content": payload.message,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    history = history[-40:]

    try:
        result = await generate_reply(
            user_message=payload.message,
            user_name=payload.user_name or "Visitor",
            history=history[:-1],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI error: {exc}")

    raw_answer = result.get("answer", "").strip() or "Sorry, please try again."

    lead = extract_lead(raw_answer)
    status = "Booked" if lead else "Interested"

    if lead:
        await send_lead_to_sheets(lead, session_id)

    clean_answer = strip_lead_block(raw_answer)
    if lead and not clean_answer:
        clean_answer = f"Thank you, {lead['name']}! Our team member will contact you soon. 🌿"

    history.append({
        "role": "assistant",
        "content": clean_answer,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    SESSIONS[session_id] = history

    return ChatMessageOut(
        session_id=session_id,
        answer=clean_answer,
        status=status,
        service=lead["service"] if lead else "",
        name=lead["name"] if lead else "",
    )


@app.post("/api/session/reset")
async def reset_session(session_id: str):
    SESSIONS.pop(session_id, None)
    return {"status": "reset"}