import re
from openai import AsyncOpenAI
from config import settings
from prompts.system_prompt import SYSTEM_PROMPT


_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


STATUS_RE = re.compile(r"##\s*STATUS\s*:\s*(booked|book|interested|spam)\s*##", re.IGNORECASE)
SERVICE_RE = re.compile(
    r"(?:^|\n)\s*[*_~`]*\s*(?:Course|Service)\s*[*_~`]*\s*:\s*([^\n]+)",
    re.IGNORECASE,
)


def _clean(answer: str) -> str:
    txt = answer or ""
    txt = txt.replace("```", "")
    txt = re.sub(r"##\s*STATUS\s*:[^#\n]*##", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"##[^#\n]{1,120}##", "", txt)
    txt = re.sub(r"#{1,2}\s*STATUS\s*:[^\n]*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(
        r"^\s*[*_~`]*\s*(?:Course|Service)\s*[*_~`]*\s*:\s*.*$",
        "", txt, flags=re.IGNORECASE | re.MULTILINE,
    )
    txt = re.sub(r"^\s*#{1,6}\s+", "", txt, flags=re.MULTILINE)
    txt = re.sub(r"[*_~`]+", "", txt)
    txt = re.sub(r"^\s*[-*_]{3,}\s*$", "", txt, flags=re.MULTILINE)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def _extract_status(answer: str) -> str:
    m = STATUS_RE.search(answer or "")
    if not m:
        return "Interested"
    s = m.group(1).lower()
    if s in ("book", "booked"):
        return "Booked"
    if s == "spam":
        return "Spam"
    return "Interested"


def _extract_service(answer: str) -> str:
    m = SERVICE_RE.search(answer or "")
    return m.group(1).strip() if m else ""


async def generate_reply(
    user_message: str,
    user_name: str = "Website Visitor",
    history: list | None = None,
) -> dict:
    history = history or []
    user_ctx = f"Customer Name: {user_name}\nCustomer Message: {user_message}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = (turn.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_ctx})

    completion = await _client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=1200,
    )

    raw = completion.choices[0].message.content or ""
    return {
        "answer": _clean(raw),
        "status": _extract_status(raw),
        "service": _extract_service(raw),
    }