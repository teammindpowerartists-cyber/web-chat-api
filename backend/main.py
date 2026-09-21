import os
import re
import uuid
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schemas import ChatMessageIn, ChatMessageOut, HealthOut
from config import settings

# Try to import AI client — but don't crash if it's unavailable
try:
    from services.ai_client import generate_reply
    AI_AVAILABLE = True
except Exception:
    AI_AVAILABLE = False
    async def generate_reply(*args, **kwargs):
        raise RuntimeError("AI client not available")


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

# =================================================================
# SERVICE DATA
# =================================================================
SERVICES = {
    "Telepathy Behavior Modification": {
        "price": "$250/month",
        "keywords": ["telepathy behavior", "telepathy service", "telepathy program", "telepathy"],
        "en": "🧠 **Telepathy Behavior Modification** — $250/month\n\nA remote Mind Power program using telepathy-oriented practices, focused intention and energy-based techniques to support healthier behavioral patterns. Suited to situations involving relationship behavior, or concerns such as aggression, withdrawal and difficult behavioral patterns in adolescents or young adults.\n\nAppropriate professional care is recommended where behavioral or mental-health concerns are significant. This is complementary work and does not override another person's free will.",
        "ur": "🧠 **Telepathy Behavior Modification** — $250/month\n\nYeh ek remote Mind Power program hai jo telepathy-oriented practices, focused intention aur energy-based techniques istemal karta hai — maqsad behtar behavioral patterns ko support karna hai. Yeh un situations ke liye hai jin mein relationship behavior ya aggression, withdrawal aur mushkil behavioral patterns (khaas tor par adolescents ya young adults mein) shamil hon.\n\nYeh complementary kaam hai aur kisi doosre ki free will ko override nahi karta.",
    },
    "Daily Hormonal Healing": {
        "price": "$250/month",
        "keywords": ["hormonal healing", "hormone healing", "hormonal imbalance", "hormone imbalance", "hormonal"],
        "en": "⚖️ **Daily Hormonal Healing** — $250/month\n\nA daily remote energy and spiritual healing program for hormonal imbalance and its associated effects on overall wellbeing. Typically continued for 2–3 months, supporting greater mind-body balance alongside appropriate medical care.\n\nHormonal symptoms can have medical causes — we recommend a proper medical assessment alongside this complementary program.",
        "ur": "⚖️ **Daily Hormonal Healing** — $250/month\n\nYeh ek daily remote energy aur spiritual healing program hai jo hormonal imbalance aur uske asraat par kaam karta hai. Aam tor par 2–3 months tak jari rehta hai, mind-body balance ko support karta hai — saath hi appropriate medical care ke saath.\n\nHormonal symptoms ki medical wajuhaat bhi ho sakti hain — hum medical assessment ki sifarish karte hain.",
    },
    "Aura Cleansing & Energy Boosting": {
        "price": "$125/session",
        "keywords": ["aura cleansing", "aura healing", "aura boost", "aura"],
        "en": "✨ **Aura Cleansing & Energy Boosting** — $125/session\n\nA focused remote or live energy session for comprehensive cleansing and strengthening of the aura. Works with both the magnetic/energetic and spiritual dimensions, clearing accumulated energetic heaviness and creating a stronger, fresher, more balanced state.",
        "ur": "✨ **Aura Cleansing & Energy Boosting** — $125/session\n\nYeh ek focused remote ya live energy session hai jo aapke aura ki comprehensive safai aur strengthening ke liye hai. Magnetic/energetic aur spiritual dimensions dono par kaam karta hai — accumulated energetic heaviness ko clear karke stronger, fresher aur balanced state banata hai.",
    },
    "Remote Emotional & Psychological Healing": {
        "price": "$250/month",
        "keywords": ["emotional healing", "emotional support", "psychological healing"],
        "en": "💙 **Remote Emotional & Psychological Healing** — $250/month\n\nA non-conversational, complementary approach to emotional and psychological wellbeing. Sufi Awaisi remotely works with you through Mind Power, energy and spiritual healing practices — supporting emotional balance, mental calmness and relief from accumulated psychological burden.",
        "ur": "💙 **Remote Emotional & Psychological Healing** — $250/month\n\nYeh ek non-conversational, complementary approach hai emotional aur psychological wellbeing ke liye. Sufi Awaisi remotely Mind Power, energy aur spiritual healing practices ke zariye aapke saath kaam karte hain — emotional balance, mental calmness aur accumulated psychological burden se rahat ke liye.",
    },
    "Hypnotherapy": {
        "price": "$200/session",
        "keywords": ["hypnotherapy", "hypnosis", "hypno therapy"],
        "en": "🧠 **Hypnotherapy** — $200/session\n\nA personalized one-to-one session designed around your specific objective. Deep relaxation, focused attention, therapeutic suggestions, visualization and subconscious-mind techniques work on relevant patterns, beliefs, habits and personal-development challenges.\n\nEspecially suited for a specific goal: limiting beliefs, confidence, fears, procrastination, habits, motivation, self-esteem, performance, or mental blocks.",
        "ur": "🧠 **Hypnotherapy** — $200/session\n\nYeh ek personalized one-to-one session hai jo aapke specific objective ke around design ki gayi hai. Deep relaxation, focused attention, therapeutic suggestions, visualization aur subconscious-mind techniques — relevant patterns, beliefs, habits aur personal-development challenges par kaam karte hain.\n\nSpecific goals ke liye behtareen: limiting beliefs, confidence, fears, procrastination, habits, motivation, self-esteem, performance ya mental blocks.",
    },
    "Remote Relationship Healing": {
        "price": "$400/month",
        "keywords": ["relationship healing", "marriage healing", "couple healing"],
        "en": "💞 **Remote Relationship Healing** — $400/month\n\nA remote energy and spiritual wellness program focused on two individuals within a relationship. The work aims to reduce emotional and psychological barriers, support greater inner balance, and create conditions more conducive to healthier communication, understanding and relationship harmony.\n\nThis is complementary support. It does not guarantee reconciliation, love, or changes in another person's free choice.",
        "ur": "💞 **Remote Relationship Healing** — $400/month\n\nYeh ek remote energy aur spiritual wellness program hai jo ek relationship mein do afraad par focus karta hai. Maqsad emotional aur psychological rukawatein kam karna, inner balance support karna aur behtar communication, samajh aur harmony ke liye conditions banana hai.\n\nYeh complementary support hai. Yeh reconciliation, love ya kisi doosre ke free choice mein tabdeeli ki guarantee nahi deta.",
    },
    "Daily Mind Strengthening Healing": {
        "price": "$250/month",
        "keywords": ["mind strengthening", "mind healing", "mental healing", "mental clarity", "mental exhaustion", "mind fog", "brain fog", "overthinking", "focus problem"],
        "en": "🎯 **Daily Mind Strengthening Healing** — $250/month\n\nA daily remote Mind Power, energy and spiritual healing program for mental exhaustion, demanding workloads, overthinking, reduced focus or brain fog. Designed to support mental freshness, resilience, clarity, focus and a stronger everyday mental state.\n\nEspecially relevant for professionals, entrepreneurs, executives and students dealing with cognitive overload.",
        "ur": "🎯 **Daily Mind Strengthening Healing** — $250/month\n\nYeh ek daily remote Mind Power, energy aur spiritual healing program hai — mental exhaustion, demanding workloads, overthinking, reduced focus ya brain fog ke liye. Maqsad hai mental freshness, resilience, clarity, focus aur ek stronger everyday mental state.\n\nKhaas tor par professionals, entrepreneurs, executives aur students ke liye jo cognitive overload se guzar rahe hain.",
    },
    "Remote Skin & Hair Healing": {
        "price": "$250/month",
        "keywords": ["hair fall", "hair healing", "hair loss", "skin healing", "skin & hair", "skin and hair"],
        "en": "🌿 **Remote Skin & Hair Healing** — $250/month\n\nA remote complementary Mind Power, energy and spiritual wellness program focused on supporting skin and hair wellbeing. Intended for concerns such as hair fall, hair vitality and overall skin appearance, while continuing any appropriate dermatological or medical care.\n\nHair and skin concerns can have medical, hormonal, nutritional or genetic causes — we encourage appropriate medical evaluation alongside this complementary program.",
        "ur": "🌿 **Remote Skin & Hair Healing** — $250/month\n\nYeh ek remote complementary Mind Power, energy aur spiritual wellness program hai jo skin aur hair ki behtari par focus karta hai. Hair fall, hair vitality aur overall skin appearance jaise concerns ke liye — apni dermatological ya medical care jari rakhte hue.\n\nHair aur skin concerns ki medical, hormonal, nutritional ya genetic wajuhaat ho sakti hain — hum appropriate medical evaluation ki sifarish karte hain.",
    },
    "Personalized Recorded Affirmations": {
        "price": "$200/topic",
        "keywords": ["affirmation", "8d", "recorded affirmation"],
        "en": "🎧 **Personalized Recorded Affirmations** — $200/topic\n\nA personalized recorded affirmation program professionally prepared around one specific goal or area of transformation. The wording and suggestions are customized for you and designed for repeated listening to reinforce constructive thoughts, beliefs and subconscious patterns.\n\nSuitable for: confidence, self-worth, motivation, success mindset, financial mindset, discipline, focus, positive self-image or goal achievement.",
        "ur": "🎧 **Personalized Recorded Affirmations** — $200/topic\n\nYeh ek personalized recorded affirmation program hai jo ek specific goal ya transformation ke area ke around professionally tayyar kiya jata hai. Words aur suggestions aapke liye customize kiye jate hain — repeated listening se constructive thoughts, beliefs aur subconscious patterns reinforce hote hain.\n\nBehtar hai: confidence, self-worth, motivation, success mindset, financial mindset, discipline, focus ya goal achievement ke liye.",
    },
    "HypnoSlim": {
        "price": "$250/session",
        "keywords": ["hypnoslim", "hypno slim", "weight loss", "weight management", "overweight"],
        "en": "⚖️ **HypnoSlim — Weight Loss Through Hypnotherapy** — $250/session\n\nA specialized hypnotherapy program addressing the mental and behavioral dimensions of weight management — including eating patterns, cravings, motivation, self-control, consistency and subconscious associations with food. Supports healthier lifestyle change alongside appropriate nutrition, exercise and medical guidance.",
        "ur": "⚖️ **HypnoSlim — Weight Loss Through Hypnotherapy** — $250/session\n\nYeh ek specialized hypnotherapy program hai jo weight management ke mental aur behavioral pehlu ko address karta hai — eating patterns, cravings, motivation, self-control, consistency aur food ke saath subconscious associations. Healthier lifestyle change ko support karta hai — appropriate nutrition, exercise aur medical guidance ke saath.",
    },
    "Daily Energy Healing Support": {
        "price": "$250/month",
        "keywords": ["energy healing", "energy support", "energy boost", "daily energy"],
        "en": "🌟 **Daily Energy Healing Support** — $250/month\n\nA 30-session remote healing program personally conducted by Sufi Awaisi, with energy, spiritual and Mind Power healing provided on a daily basis. Comprehensive support for physical, mental, emotional and psychological wellbeing, with an overall focus on restoring balance, vitality and inner strength.",
        "ur": "🌟 **Daily Energy Healing Support** — $250/month\n\nYeh Sufi Awaisi ka 30-session remote healing program hai — energy, spiritual aur Mind Power healing daily provide ki jati hai. Jismani, zehni, jazbati aur nafsiyati behtari ke liye comprehensive support — overall balance, vitality aur inner strength bahal karne par focus.",
    },
}

BOOKING_INTENT_KEYWORDS = [
    "book", "booking", "book karna", "booking karni", "book kaise",
    "booking kaise", "contact", "talk to someone", "talk to human",
    "speak to someone", "want to proceed", "want to sign", "sign me up",
    "want to start", "want to go ahead", "i want to book", "proceed",
    "get started", "mujy book", "book chahiye", "book karni hai",
]

ESCAPE_KEYWORDS = [
    "tell me", "what is", "what are", "what do", "how do", "how does",
    "explain", "about", "different question", "cancel", "stop",
    "never mind", "leave it", "forget it", "not now", "later",
    "services", "pricing", "price", "cost", "fee", "office", "location",
    "founder", "review", "testimonial", "who is", "list",
]


# =================================================================
# HELPERS
# =================================================================
def is_roman_urdu(message: str) -> bool:
    """Detect Roman Urdu vs English."""
    msg = message.lower()
    roman_urdu_markers = [
        "mujy", "mujhe", "mera", "meri", "kya", "kaise", "konsi", "kaun",
        "chahiye", "chaiye", "nahi", "hai", "hoon", "hun", "karna", "karni",
        "kron", "krni", "karun", "bata", "batao", "batayein", "smj", "salam",
        "assalam", "shukriya", "aap", "ap", "apki", "aapki", "mery", "mere",
        "thakan", "thak", "wazan", "shadi", "shohar", "biwi", "darr",
    ]
    words = re.findall(r"[a-zA-Z]+", msg)
    if not words:
        return False
    urdu_count = sum(1 for w in words if w in roman_urdu_markers)
    return urdu_count >= 1


def detect_service(message: str):
    """Return (service_name, service_data) if matched, else (None, None)."""
    msg_lower = message.lower().strip()
    best_match = None
    best_len = 0
    for name, data in SERVICES.items():
        for kw in data["keywords"]:
            if kw in msg_lower and len(kw) > best_len:
                best_match = name
                best_len = len(kw)
    if best_match:
        return best_match, SERVICES[best_match]
    return None, None


def has_booking_intent(message: str) -> bool:
    msg_lower = message.lower().strip()
    return any(kw in msg_lower for kw in BOOKING_INTENT_KEYWORDS)


def looks_like_phone(message: str) -> bool:
    return len(re.sub(r"\D", "", message)) >= 7


def looks_like_name(message: str) -> bool:
    text = message.strip()
    if not text or len(text) > 60:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    if "?" in text or "!" in text:
        return False
    name, _ = detect_service(text)
    if name:
        return False
    words = text.split()
    if not (1 <= len(words) <= 4):
        return False
    return all(re.sub(r"[.\-']", "", w).isalpha() for w in words)


def is_escaping_flow(message: str) -> bool:
    msg = message.lower().strip()
    if "?" in msg and len(msg) > 12:
        return True
    if len(msg) > 40:
        return True
    if any(kw in msg for kw in ESCAPE_KEYWORDS):
        return True
    return False


# =================================================================
# RULE-BASED FALLBACK RESPONSES
# =================================================================
def build_service_list(lang: str) -> str:
    if lang == "ur":
        lines = ["Mind Power Artists 11 international premium services offer karta hai:\n"]
        for name, data in SERVICES.items():
            lines.append(f"• **{name}** — {data['price']}")
        lines.append("\nThora bata dein ke aap kis cheez par kaam karna chahte hain? Phir main behtareen fit recommend kar sakta hoon. 🌿")
        return "\n".join(lines)
    else:
        lines = ["Mind Power Artists offers 11 international premium services:\n"]
        for name, data in SERVICES.items():
            lines.append(f"• **{name}** — {data['price']}")
        lines.append("\nCould you tell me a bit about what you'd like to work on? That way I can recommend the best fit. 🌿")
        return "\n".join(lines)


def build_founder(lang: str) -> str:
    if lang == "ur":
        return ("Syed Asif Hussain — Sufi Awaisi ke naam se mashhoor — Mind Power Artists ke Founder & CEO hain.\n\n"
                "Woh ek Executive Coach, Human Performance Specialist, Master Trainer of Mind Sciences, Professional Hypnotherapist aur Author hain. 10+ saal ka tajurba hai aur 50,000+ logon ko train kiya hai — Pakistan aur internationally.\n\n"
                "Kya aap hamari services ke baare mein jaanna chahenge? 🌿")
    return ("Syed Asif Hussain — known as Sufi Awaisi — is the Founder & CEO of Mind Power Artists.\n\n"
            "He is an Executive Coach, Human Performance Specialist, Master Trainer of Mind Sciences, Professional Hypnotherapist, and Author. With 10+ years of experience and 50,000+ individuals trained across Pakistan and internationally.\n\n"
            "Would you like to know more about our services? 🌿")


def build_pricing(lang: str) -> str:
    if lang == "ur":
        return ("Hamari services $125 per session se $400 per month tak hain — program ke hisaab se.\n\n"
                "Kisi specific service ki exact pricing ke liye, uska naam bata dein — jaise 'Hypnotherapy' ya 'Relationship Healing' — main details share kar dunga.\n\n"
                "Ya 'contact' type karein agar aap chahte hain ke hamari team aap se rabta kare. 🌿")
    return ("Our services range from $125 per session to $400 per month, depending on the program.\n\n"
            "For exact pricing on a specific service, just name it — for example 'Hypnotherapy' or 'Relationship Healing' — and I'll share the details.\n\n"
            "Or type 'contact' if you'd like our team to reach out to you directly. 🌿")


def build_office(lang: str) -> str:
    if lang == "ur":
        return ("Hamari office timings Monday se Friday, 10:00 AM se 5:00 PM PST hain.\n\n"
                "📍 Location: The Plazzo, Below Askari Bank, Gulberg Greens, Islamabad, Pakistan\n\n"
                "Visit sirf appointment ke zariye hoti hai, kam az kam ek din pehle. 🌿")
    return ("Our office timings are Monday to Friday, 10:00 AM to 5:00 PM PST.\n\n"
            "📍 Location: The Plazzo, Below Askari Bank, Gulberg Greens, Islamabad, Pakistan\n\n"
            "Visits are by appointment only, at least one day in advance. 🌿")


def build_reviews(lang: str) -> str:
    return ("You can check client reviews and testimonials on our platforms:\n\n"
            "🌐 https://mindpowerartists.com\n"
            "📸 https://www.instagram.com/mindpowerartists_\n"
            "👍 https://facebook.com/mindpowerartists\n"
            "▶️ https://youtube.com/@mindpowerartists")


def build_greeting(lang: str) -> str:
    if lang == "ur":
        return "Mind Power Artists mein khush aamdeed! 🌿 Main OG hoon, aapka MPA AI assistant. Aaj main aapki kaise madad kar sakta hoon?"
    return "Welcome to Mind Power Artists! 🌿 I'm OG, your MPA AI assistant. How can I help you today?"


def build_personal_concern_response(message: str, lang: str) -> str:
    """Warm response for trauma / depression / anxiety / relationship / etc."""
    msg = message.lower()

    # Crisis
    if any(k in msg for k in ["suicide", "kill myself", "end my life", "self harm", "self-harm"]):
        if lang == "ur":
            return ("Yeh baat batane ka shukriya. Agar aap crisis mein hain, baraye meharbani foran local emergency service ya mental-health helpline se rabta karein — aapki safety sabse pehle hai. Aap akelay nahi hain. 🌿")
        return ("I'm really glad you told me. Please, if you're in crisis, reach out to a local emergency service or a mental-health helpline right away — your safety comes first. You are not alone. 🌿")

    # Exhaustion / tiredness / burnout — broad depletion → Daily Energy Healing
    if any(k in msg for k in [
        "exhaust", "tired", "thakan", "thak", "fatigue", "drained",
        "burnout", "burn out", "burned out", "no energy", "low energy",
    ]):
        if lang == "ur":
            return ("Yeh baat share karne ka shukriya. Har waqt thaka hua mehsoos karna waqai bohat mushkil hota hai.\n\n"
                    "Aapki situation ke liye hamari **Daily Energy Healing Support** ($250/month) sabse behtar fit hai — yeh Sufi Awaisi ka 30-session remote program hai jo jismani, zehni, jazbati aur nafsiyati behtari par comprehensive support deta hai. Iska maqsad overall balance, vitality aur inner strength bahal karna hai.\n\n"
                    "Yeh complementary kaam hai — yeh professional medical ya psychological care ka replacement nahi.\n\n"
                    "Kya aap chahenge ke main is program ki mazeed tafseel bataun? 🌿")
        return ("Thank you for sharing that. Feeling exhausted all the time can be really overwhelming — it's a heavy thing to carry.\n\n"
                "Based on what you're describing, the best fit is our **Daily Energy Healing Support** ($250/month) — a 30-session remote program by Sufi Awaisi designed as comprehensive support for physical, mental, emotional, and psychological wellbeing. It focuses on restoring overall balance, vitality and inner strength.\n\n"
                "This is complementary work — it supports, but does not replace, professional medical or psychological care.\n\n"
                "Would you like more details on this service? 🌿")

    # Trauma
    if any(k in msg for k in ["trauma", "ptsd", "abuse"]):
        if lang == "ur":
            return ("Yeh baat share karne ka shukriya. Jo aap se guzra woh bohat bhaari lagta hai — aur yeh baat karna himmat ka kaam hai.\n\n"
                    "Mind Power Artists mein hum mind, subconscious aur energy systems par kaam karte hain takay inner balance support ho. Hamara kaam complementary hai — yeh professional mental-health care ka replacement nahi.\n\n"
                    "Kya aap chahenge ke main aapko batayein hum kaise support kar sakte hain? 🌿")
        return ("Thank you for sharing that with me. What you've been through sounds really heavy — and it takes courage to talk about it.\n\n"
                "At Mind Power Artists, we work with the mind, subconscious and energy systems to support inner balance. Our work is complementary — it supports, but does not replace, professional mental-health care.\n\n"
                "Would you like to know how we might support you? 🌿")

    # Depression
    if any(k in msg for k in ["depression", "depressed", "feeling low", "hopeless"]):
        if lang == "ur":
            return ("Yeh baat share karne ka shukriya. Aisa mehsoos karna bohat mushkil hota hai.\n\n"
                    "Baraye meharbani apni professional mental-health support jari rakhein. Iske saath, Mind Power Artists subconscious mind aur energy systems par kaam karta hai — complementary support for inner balance.\n\n"
                    "Kya aap chahenge ke main aapko aur batayein? 🌿")
        return ("I'm sorry you're feeling this way. Depression can feel isolating and exhausting — thank you for trusting me with that.\n\n"
                "Please continue with any professional mental-health support you have. Alongside that, our work at Mind Power Artists focuses on the subconscious mind and energy systems — complementary support for inner balance.\n\n"
                "Would you like to know how we might support you? 🌿")

    # Relationship / marriage
    if any(k in msg for k in ["marriage", "husband", "wife", "relationship", "shadi", "shohar", "biwi", "divorce"]):
        if lang == "ur":
            return ("Yeh waqai bohat mushkil hai. Shadi mein masail bohat takleef deh hote hain — yeh baat share karne ka shukriya.\n\n"
                    "Kyunke yeh do logon aur aapke darmiyan taaluq ka masla hai, hamari **Remote Relationship Healing** ($400/month) sabse munasib program hai. Yeh remote energy aur spiritual wellness program hai jo do afraad ke darmiyan emotional barriers kam karne aur behtar communication aur harmony ko support karne par focus karta hai.\n\n"
                    "Yeh complementary support hai — yeh reconciliation ya kisi doosre ke faislay mein tabdeeli ki guarantee nahi deta. Kya aap chahenge ke main is program ki mazeed tafseel bataun? 🌿")
        return ("That sounds really difficult. Feeling unheard or disconnected in a marriage can be painful and lonely — thank you for sharing that with me.\n\n"
                "Since this involves two people and the connection between you, our **Remote Relationship Healing** ($400/month) is the most relevant program. It's a remote energy and spiritual wellness program focused on reducing emotional barriers and supporting healthier communication and harmony.\n\n"
                "It's complementary support — it doesn't guarantee reconciliation or change another person's free choice. Would you like more details on this program? 🌿")

    # Anxiety / stress
    if any(k in msg for k in ["anxiety", "anxious", "stress", "stressed", "worry", "tension"]):
        if lang == "ur":
            return ("Yeh baat share karne ka shukriya. Continuous anxiety bohat thaka dene wali hoti hai.\n\n"
                    "Mind Power Artists mein hum mind, subconscious aur energy systems par kaam karte hain takay inner calm aur balance support ho. Hamara kaam complementary hai.\n\n"
                    "Aapke liye **Remote Emotional & Psychological Healing** ($250/month) ya **Daily Mind Strengthening Healing** ($250/month) fit ho sakta hai. Kya aap chahenge ke main in ke baare mein batayein? 🌿")
        return ("Thank you for sharing that with me. Ongoing anxiety can be really exhausting — you're not alone in this.\n\n"
                "At Mind Power Artists, we work with the mind, subconscious and energy systems to support inner calm and balance. Our work is complementary.\n\n"
                "For you, **Remote Emotional & Psychological Healing** ($250/month) or **Daily Mind Strengthening Healing** ($250/month) may be a good fit. Would you like to know more about either? 🌿")

    # Weight
    if any(k in msg for k in ["weight", "overweight", "fat", "obese", "wazan"]):
        if lang == "ur":
            return ("Wazan ke masail bohat bhaari hote hain — yeh baat share karne ka shukriya.\n\n"
                    "Hamari **HypnoSlim — Weight Loss Through Hypnotherapy** ($250/session) iska mental aur behavioral side address karti hai — eating patterns, cravings, motivation, self-control aur food ke saath subconscious associations. Yeh appropriate nutrition, exercise aur medical guidance ke saath best kaam karti hai.\n\n"
                    "Kya aap chahenge ke main is program ki mazeed tafseel bataun? 🌿")
        return ("Weight struggles can be really heavy to carry — I'm glad you told me.\n\n"
                "Our **HypnoSlim — Weight Loss Through Hypnotherapy** ($250/session) addresses the mental and behavioral side of weight management — eating patterns, cravings, motivation, self-control and subconscious associations with food. It works best alongside appropriate nutrition, exercise and medical guidance.\n\n"
                "Would you like more details on this program? 🌿")

    # Confidence
    if any(k in msg for k in ["confidence", "self esteem", "self-esteem", "self worth", "self-worth", "shy"]):
        if lang == "ur":
            return ("Yeh baat share karne ka shukriya. Self-doubt bohat thaka dene wala hota hai.\n\n"
                    "Aapke liye **Hypnotherapy** ($200/session) ya **Personalized Recorded Affirmations** ($200/topic) behtar fit ho sakti hain. Hypnotherapy specific patterns par interactive kaam karti hai; affirmations repeated self-programming ke liye hain.\n\n"
                    "Kya aap chahenge ke main yeh dono options ke baare mein batayein? 🌿")
        return ("Thank you for telling me. Self-doubt can be really draining — you're not alone in feeling this way.\n\n"
                "For you, **Hypnotherapy** ($200/session) or **Personalized Recorded Affirmations** ($200/topic) may be a good fit. Hypnotherapy works interactively on specific patterns; affirmations are designed for repeated self-programming around a goal.\n\n"
                "Would you like to know more about either option? 🌿")

    # Fear / phobia
    if any(k in msg for k in ["fear", "phobia", "afraid", "scared", "darr"]):
        if lang == "ur":
            return ("Yeh baat share karne ka shukriya. Specific fears bohat real aur challenging hotay hain.\n\n"
                    "Aapke liye **Hypnotherapy** ($200/session) behtar fit hai — personalized one-to-one session jahan Sufi Awaisi deep relaxation, focused attention aur therapeutic suggestion ke zariye aapke specific fear par kaam karte hain.\n\n"
                    "Kya aap chahenge ke main is session ke baare mein aur batayein? 🌿")
        return ("Thanks for sharing. Specific fears can feel very real and limiting.\n\n"
                "For you, **Hypnotherapy** ($200/session) is the best fit — a personalized one-to-one session where Sufi Awaisi works with deep relaxation, focused attention and therapeutic suggestion to address the specific fear you're carrying.\n\n"
                "Would you like to know more about this session? 🌿")

    # Default personal concern
    if lang == "ur":
        return ("Yeh baat share karne ka shukriya. Jo aap se guzar raha hai woh ahem hai.\n\n"
                "Mind Power Artists mein hum mind, subconscious aur energy systems par kaam karte hain takay inner balance support ho. Hamara kaam complementary hai — professional medical ya psychological care ka replacement nahi.\n\n"
                "Kya aap thora aur bata sakte hain ke aap kis cheez par kaam karna chahte hain? Phir main sahi service recommend kar sakta hoon. 🌿")
    return ("Thank you for sharing that with me. What you're going through matters.\n\n"
            "At Mind Power Artists, we work with the mind, subconscious and energy systems to support inner balance. Our work is complementary — it supports, but does not replace, professional medical or psychological care.\n\n"
            "Could you tell me a bit more about what you'd like to work on? That way I can recommend the right service for you. 🌿")


def fallback_response(message: str) -> str:
    """Rule-based fallback that works 100% without AI."""
    msg = message.lower().strip()
    lang = "ur" if is_roman_urdu(message) else "en"

    # 1. Crisis — check FIRST before anything
    if any(k in msg for k in ["suicide", "kill myself", "end my life", "self harm", "self-harm"]):
        return build_personal_concern_response(message, lang)

    # 2. Greeting (short message with greeting word)
    greetings = ["hi", "hello", "hey", "salam", "assalam", "helo", "hii", "hy"]
    if len(msg) < 20:
        for g in greetings:
            if msg == g or msg.startswith(g + " ") or msg.startswith(g + ",") or msg.startswith(g + "!"):
                return build_greeting(lang)

    # 3. Service-specific question
    name, data = detect_service(message)
    if name:
        return data[lang]

    # 4. All services / list — includes bare words
    bare_service_words = {"services", "service", "list", "menu", "help", "options", "info", "information", "s"}
    service_list_phrases = [
        "all services", "what services", "services list", "sare services",
        "which services", "list of services", "tell me about services",
        "what do you offer", "what do you provide", "available services",
        "show services", "your services", "tell me about all", "our services",
    ]
    if msg in bare_service_words or any(k in msg for k in service_list_phrases):
        return build_service_list(lang)

    # 5. Founder
    if any(k in msg for k in [
        "founder", "sufi awaisi", "who runs", "owner", "ceo",
        "about mpa", "about mind power", "who is behind", "kaun hai",
        "aap kaun", "aap kon",
    ]):
        return build_founder(lang)

    # 6. Pricing — includes bare words
    bare_pricing_words = {"pricing", "price", "prices", "cost", "fees", "fee", "charges", "rate", "rates"}
    pricing_phrases = [
        "how much", "cost of", "your fees", "your charges", "price list",
        "all prices", "qeemat", "kitna",
    ]
    if msg in bare_pricing_words or any(k in msg for k in pricing_phrases):
        return build_pricing(lang)

    # 7. Office
    if any(k in msg for k in [
        "office", "location", "address", "where are you", "visit",
        "timing", "hours", "kahan",
    ]):
        return build_office(lang)

    # 8. Reviews
    if any(k in msg for k in ["review", "reviews", "testimonial", "trust", "feedback", "rating"]):
        return build_reviews(lang)

    # 9. Personal concerns — warm response
    personal_markers = [
        "trauma", "ptsd", "depress", "anxiety", "anxious", "stress",
        "marriage", "husband", "wife", "relationship", "shadi", "shohar",
        "weight", "wazan", "confidence", "self esteem", "fear", "phobia",
        "afraid", "darr", "grief", "loss", "lonely", "sad",
        "exhaust", "tired", "thakan", "thak", "fatigue", "drained",
        "burnout", "burn out", "burned out", "no energy", "low energy",
        "always tired", "always exhausted", "never have energy",
    ]
    if any(k in msg for k in personal_markers):
        return build_personal_concern_response(message, lang)

    # 10. Default
    if lang == "ur":
        return ("Main Mind Power Artists ki services mein madad kar sakta hoon. "
                "Aap hamari services, pricing, ya founder ke baare mein pooch sakte hain — "
                "ya 'contact' type karein takay hamari team aap se rabta kare. 🌿")
    return ("I'm here to help with Mind Power Artists' services. "
            "You can ask me about our programs, pricing, or the founder — "
            "or type 'contact' to leave your details with our team. 🌿")


# =================================================================
# LEAD CAPTURE
# =================================================================
async def send_lead_to_sheets(lead: dict, session_id: str) -> bool:
    payload = {
        "session_id": session_id,
        "name": lead["name"],
        "phone": lead["phone"],
        "service": lead["service"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    if not LEAD_WEBHOOK_URL:
        print(f"[LEAD-FALLBACK] No LEAD_WEBHOOK_URL — dumping lead:")
        print(f"[LEAD-FALLBACK] {payload}")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(LEAD_WEBHOOK_URL, json=payload)
            if r.status_code < 400:
                print(f"[LEAD] Saved → {r.status_code}")
                return True
            print(f"[LEAD-FALLBACK] Sheet returned {r.status_code}. Dumping lead:")
            print(f"[LEAD-FALLBACK] {payload}")
            return False
    except Exception as e:
        print(f"[LEAD-FALLBACK] Webhook failed: {e}. Dumping lead:")
        print(f"[LEAD-FALLBACK] {payload}")
        return False


# =================================================================
# ROUTES
# =================================================================
@app.get("/")
async def root():
    return {"status": "MPA Chatbot API", "version": "1.0.0", "model": settings.OPENAI_MODEL, "ai_available": AI_AVAILABLE}


@app.get("/health", response_model=HealthOut)
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            )
        reachable = r.status_code < 500 and r.status_code != 401
    except Exception:
        reachable = False
    return HealthOut(status="ok", openai_reachable=reachable)


@app.post("/api/chat", response_model=ChatMessageOut)
async def chat(payload: ChatMessageIn):
    session_id = payload.session_id.strip() or str(uuid.uuid4())
    message = payload.message.strip()

    state = SESSIONS.get(session_id)
    if not state:
        state = {"history": [], "booking": None}
        SESSIONS[session_id] = state

    history = state["history"]
    booking = state["booking"]

    history.append({
        "role": "user", "content": message,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    history[:] = history[-40:]

    # ===========================================================
    # CASE 1: Active booking flow
    # ===========================================================
    if booking is not None:
        if is_escaping_flow(message):
            state["booking"] = None
            print(f"[FLOW-ESCAPE] User escaped booking flow: '{message}'")
        else:
            service = booking.get("service") or ""
            name = booking.get("name") or ""
            phone = booking.get("phone") or ""

            # STEP 0 — waiting for service name
            if not service:
                detected, _ = detect_service(message)
                booking["service"] = detected if detected else message.strip()
                reply = "I'd be glad to arrange this for you. Our team member will contact you personally. Could you please share your full name?"
                history.append({"role": "assistant", "content": reply, "ts": datetime.now(timezone.utc).isoformat()})
                return ChatMessageOut(
                    session_id=session_id, answer=reply, status="Interested",
                    service=booking["service"], name="",
                )

            # STEP 1 — waiting for name
            if not name:
                if looks_like_phone(message):
                    booking["phone"] = message
                    reply = "Thank you. And could you please share your full name?"
                else:
                    booking["name"] = message
                    reply = f"Thank you, {message}. And your phone number with country code?"

            # STEP 2 — waiting for phone
            elif not phone:
                if looks_like_phone(message):
                    booking["phone"] = message
                    await send_lead_to_sheets(
                        {"name": booking["name"], "phone": booking["phone"], "service": booking["service"]},
                        session_id,
                    )
                    reply = f"Thank you, {booking['name']}! Our team member will contact you soon regarding {booking['service']}. 🌿"
                    state["booking"] = None
                else:
                    reply = "Thank you. Could you please share your phone number with country code?"

            else:
                state["booking"] = None
                reply = "Thank you! Our team member will be in touch soon. 🌿"

            history.append({"role": "assistant", "content": reply, "ts": datetime.now(timezone.utc).isoformat()})
            return ChatMessageOut(
                session_id=session_id, answer=reply, status="Interested",
                service=service, name=booking.get("name", "") if booking else "",
            )

    # ===========================================================
    # CASE 2: Service name OR booking intent detected — start flow
    # ===========================================================
    detected_service, detected_data = detect_service(message)
    booking_intent = has_booking_intent(message)

    if detected_service or booking_intent:
        service = detected_service or ""
        state["booking"] = {"service": service, "name": "", "phone": ""}

        reply = (
            "I'd be glad to arrange this for you. Our team member will contact you "
            "personally. Could you please share your full name?"
        ) if service else (
            "I'd be glad to arrange this for you. Which service would you like to book?"
        )

        history.append({"role": "assistant", "content": reply, "ts": datetime.now(timezone.utc).isoformat()})
        return ChatMessageOut(
            session_id=session_id, answer=reply, status="Interested",
            service=service, name="",
        )

    # ===========================================================
    # CASE 3: Try AI; if it fails, use comprehensive rule-based fallback
    # ===========================================================
    answer = ""
    result = None
    ai_succeeded = False

    if AI_AVAILABLE:
        try:
            result = await generate_reply(
                user_message=message,
                user_name=payload.user_name or "Visitor",
                history=history[:-1],
            )
            answer = result.get("answer", "").strip()
            if answer:
                ai_succeeded = True
        except Exception as exc:
            print(f"[AI-FALLBACK] {type(exc).__name__}: {exc}")

    if not ai_succeeded:
        answer = fallback_response(message)
        print(f"[AI-FALLBACK] Rule-based response used for: '{message[:60]}'")

    history.append({"role": "assistant", "content": answer, "ts": datetime.now(timezone.utc).isoformat()})

    return ChatMessageOut(
        session_id=session_id,
        answer=answer,
        status=result.get("status", "Interested") if result else "Interested",
        service=result.get("service", "") if result else "",
        name=payload.user_name or "",
    )


@app.post("/api/session/reset")
async def reset_session(session_id: str):
    SESSIONS.pop(session_id, None)
    return {"status": "reset"}