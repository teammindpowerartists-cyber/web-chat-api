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
            user_name=payload.user_name or "Website Visitor",
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
    SESSIONS[session_id] = history

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