(function () {
  const API_URL = "https://web-chat-api-fwsg.vercel.app/api/chat";

  const SESSION_KEY = "mpa_chat_session";
  function getSessionId() {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = "web-" + Math.random().toString(36).slice(2, 12) + "-" + Date.now().toString(36);
      localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  const root = document.getElementById("mpa-chat-root") || document.body;
  const sessionId = getSessionId();

  root.insertAdjacentHTML("beforeend", `
    <button id="mpa-chat-btn" aria-label="Chat with us">
      <span class="mpa-chat-btn-icon">💬</span>
      <span class="mpa-chat-btn-label">Chat with us</span>
    </button>
    <div id="mpa-chat-panel">
      <div id="mpa-chat-header">
        <div>
          <h3>OG Support</h3>
          <small>Mind Power Artists • Online</small>
        </div>
        <button id="mpa-chat-close" aria-label="Close chat">×</button>
      </div>
      <div id="mpa-chat-msgs"></div>
      <div id="mpa-chat-input-row">
        <input id="mpa-chat-input" type="text" placeholder="Type your message..." autocomplete="off" />
        <button id="mpa-chat-send">Send</button>
      </div>
      <div id="mpa-chat-footer">Powered by Mind Power Artists</div>
    </div>
  `);

  const btn = document.getElementById("mpa-chat-btn");
  const panel = document.getElementById("mpa-chat-panel");
  const closeBtn = document.getElementById("mpa-chat-close");
  const msgs = document.getElementById("mpa-chat-msgs");
  const input = document.getElementById("mpa-chat-input");
  const sendBtn = document.getElementById("mpa-chat-send");

  let opened = false;

  function addMsg(text, cls) {
    const div = document.createElement("div");
    div.className = "mpa-msg " + cls;
    div.textContent = text;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  function isMobile() {
    return window.matchMedia("(max-width: 480px)").matches;
  }

  function openPanel() {
    panel.classList.add("open");
    if (isMobile()) document.body.classList.add("mpa-chat-open");
    setTimeout(() => input.focus(), 100);
    if (!opened) {
      opened = true;
      addMsg(
        "Welcome to Mind Power Artists! 🌿 I'm OG, your MPA AI assistant. How can I help you today?",
        "bot"
      );
    }
  }

  function closePanel() {
    panel.classList.remove("open");
    document.body.classList.remove("mpa-chat-open");
  }

  btn.addEventListener("click", () => {
    if (panel.classList.contains("open")) closePanel();
    else openPanel();
  });

  closeBtn.addEventListener("click", closePanel);

  async function send() {
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;

    addMsg(text, "user");
    const typing = addMsg("OG is typing...", "bot typing");

    // Real-time: retry once if the network hiccups
    let attempt = 0;
    const maxAttempts = 2;
    let success = false;
    let lastError = null;

    while (attempt < maxAttempts && !success) {
      attempt++;
      try {
        const res = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            message: text,
            user_name: "",
            page_url: location.href,
          }),
        });

        const data = await res.json();
        typing.remove();

        if (!res.ok) {
          lastError = `HTTP ${res.status}`;
          if (attempt < maxAttempts) {
            // Brief retry delay
            await new Promise((r) => setTimeout(r, 800));
            continue;
          }
          // Final attempt failed
          addMsg(
            "I'm having a brief technical moment right now. Please try again in a moment — " +
            "or visit www.mindpowerartists.com to reach our team directly. 🌿",
            "bot"
          );
          success = true;
          return;
        }

        addMsg(data.answer || "Sorry, I couldn't process that. Please try again.", "bot");
        success = true;
      } catch (e) {
        lastError = e.message || "network error";
        if (attempt < maxAttempts) {
          await new Promise((r) => setTimeout(r, 800));
          continue;
        }
        typing.remove();
        addMsg(
          "Looks like my connection dropped for a second. Could you try sending that again? " +
          "If it keeps happening, you can reach our team at www.mindpowerartists.com. 🌿",
          "bot"
        );
        success = true;
      } finally {
        // Only re-enable on last attempt
        if (success || attempt >= maxAttempts) {
          input.disabled = false;
          sendBtn.disabled = false;
          input.focus();
        }
      }
    }
  }

  sendBtn.addEventListener("click", send);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
})();