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

# session_id -> {"history": [...], "booking": {"service": str, "name": str, "phone": str}}
SESSIONS: dict = {}

LEAD_WEBHOOK_URL = os.getenv("LEAD_WEBHOOK_URL", "").strip()

# ---------------------------------------------------------------
# SERVICE KEYWORD DETECTION (deterministic, not AI-driven)
# ---------------------------------------------------------------
SERVICE_KEYWORDS = {
    "telepathy behavior": "Telepathy Behavior Modification",
    "telepathy service": "Telepathy Behavior Modification",
    "telepathy program": "Telepathy Behavior Modification",
    "telepathy": "Telepathy Behavior Modification",
    "hypnotherapy": "Hypnotherapy",
    "hypnosis": "Hypnotherapy",
    "hair fall": "Remote Skin & Hair Healing",
    "hair healing": "Remote Skin & Hair Healing",
    "skin healing": "Remote Skin & Hair Healing",
    "skin & hair": "Remote Skin & Hair Healing",
    "skin and hair": "Remote Skin & Hair Healing",
    "affirmation": "Personalized Recorded Affirmations",
    "8d": "Personalized Recorded Affirmations",
    "hypnoslim": "HypnoSlim",
    "weight loss": "HypnoSlim",
    "weight management": "HypnoSlim",
    "relationship healing": "Remote Relationship Healing",
    "aura cleansing": "Aura Cleansing & Energy Boosting",
    "aura healing": "Aura Cleansing & Energy Boosting",
    "aura": "Aura Cleansing & Energy Boosting",
    "hormonal healing": "Daily Hormonal Healing",
    "hormone healing": "Daily Hormonal Healing",
    "hormonal imbalance": "Daily Hormonal Healing",
    "mind strengthening": "Daily Mind Strengthening Healing",
    "brain fog": "Daily Mind Strengthening Healing",
    "mental clarity": "Daily Mind Strengthening Healing",
    "emotional healing": "Remote Emotional & Psychological Healing",
    "energy healing": "Daily Energy Healing Support",
    "energy support": "Daily Energy Healing Support",
}

BOOKING_INTENT_KEYWORDS = [
    "book", "booking", "book karna", "booking karni", "book kaise",
    "contact", "talk to someone", "talk to human", "speak to someone",
    "want to proceed", "want to sign", "sign me up", "want to start",
    "want to go ahead", "i want to book", "proceed", "get started",
]


def detect_service(message: str):
    """Return canonical service name if the message names one, else None."""
    msg_lower = message.lower().strip()
    # Sort by length desc so longer phrases match first
    for keyword in sorted(SERVICE_KEYWORDS.keys(), key=len, reverse=True):
        if keyword in msg_lower:
            return SERVICE_KEYWORDS[keyword]
    return None


def has_booking_intent(message: str) -> bool:
    msg_lower = message.lower().strip()
    return any(kw in msg_lower for kw in BOOKING_INTENT_KEYWORDS)


def looks_like_name(message: str) -> bool:
    """Rough check: 1-4 words, no digits, no question marks, not too long."""
    text = message.strip()
    if not text or len(text) > 60:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    if "?" in text or "!" in text:
        return False
    words = text.split()
    if not (1 <= len(words) <= 4):
        return False
    # All words alphabetic (allow hyphens, dots, spaces)
    return all(re.sub(r"[.\-']", "", w).isalpha() for w in words)


def looks_like_phone(message: str) -> bool:
    """Contains at least 7 digits."""
    return len(re.sub(r"\D", "", message)) >= 7


# ---------------------------------------------------------------
# LEAD CAPTURE (Google Sheets)
# ---------------------------------------------------------------
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
            print(f"[LEAD] Saved → {r.status_code}")
    except Exception as e:
        print(f"[LEAD] Webhook failed: {e}")


# ---------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------
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
    message = payload.message.strip()

    # Load or init session
    state = SESSIONS.get(session_id)
    if not state:
        state = {"history": [], "booking": None}
        SESSIONS[session_id] = state

    history = state["history"]
    booking = state["booking"]

    # Log user message
    history.append({
        "role": "user",
        "content": message,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    history[:] = history[-40:]

    # ===========================================================
    # CASE 1: We are in a booking flow — Python handles everything
    # ===========================================================
    if booking is not None:
        service = booking.get("service")
        name = booking.get("name")
        phone = booking.get("phone")

        if not name:
            # We asked for name; this message should be it
            if looks_like_phone(message):
                # User gave phone first — treat it as phone, keep asking for name
                reply = "Thank you. And could you please share your full name?"
                booking["phone"] = message
            else:
                booking["name"] = message
                reply = f"Thank you, {message}. And your phone number with country code?"
        elif not phone:
            # We asked for phone; this message should be it
            if looks_like_phone(message):
                booking["phone"] = message
                # Complete the lead
                lead = {
                    "name": booking["name"],
                    "phone": booking["phone"],
                    "service": booking["service"],
                }
                await send_lead_to_sheets(lead, session_id)
                reply = (
                    f"Thank you, {booking['name']}! Our team member will contact you soon "
                    f"regarding {booking['service']}. 🌿"
                )
                state["booking"] = None  # clear booking flow
            else:
                # User didn't give phone — ask again
                reply = (
                    f"Thank you. Could you please share your phone number with country code?"
                )
        else:
            # Safety fallback — shouldn't reach here
            state["booking"] = None
            reply = "Thank you! Our team member will be in touch soon. 🌿"

        history.append({
            "role": "assistant",
            "content": reply,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        return ChatMessageOut(
            session_id=session_id,
            answer=reply,
            status="Interested",
            service=service or "",
            name=booking.get("name", "") if booking else "",
        )

    # ===========================================================
    # CASE 2: Service name OR booking intent detected — start booking flow
    # ===========================================================
    detected_service = detect_service(message)
    booking_intent = has_booking_intent(message)

    if detected_service or booking_intent:
        service = detected_service or ""  # may be empty if just "contact"
        state["booking"] = {"service": service, "name": "", "phone": ""}

        if service:
            reply = (
                f"I'd be glad to arrange this for you. Our team member will contact you "
                f"personally. Could you please share your full name?"
            )
        else:
            # Booking intent without a service — ask which service first
            reply = (
                "I'd be glad to arrange this for you. Which service would you like to book?"
            )

        history.append({
            "role": "assistant",
            "content": reply,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        return ChatMessageOut(
            session_id=session_id,
            answer=reply,
            status="Interested",
            service=service,
            name="",
        )

    # ===========================================================
    # CASE 3: Everything else goes to the AI as before
    # ===========================================================
    try:
        result = await generate_reply(
            user_message=message,
            user_name=payload.user_name or "Visitor",
            history=history[:-1],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI error: {exc}")

    answer = result.get("answer", "").strip() or "Sorry, please try again."

    history.append({
        "role": "assistant",
        "content": answer,
        "ts": datetime.now(timezone.utc).isoformat(),
    })

    return ChatMessageOut(
        session_id=session_id,
        answer=answer,
        status=result.get("status", "Interested"),
        service=result.get("service", ""),
        name=payload.user_name or "",
    )


@app.post("/api/session/reset")
async def reset_session(session_id: str):
    SESSIONS.pop(session_id, None)
    return {"status": "reset"}