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
    <button id="mpa-chat-btn" aria-label="Open chat">💬</button>
    <div id="mpa-chat-panel">
      <div id="mpa-chat-header">
        <div>
          <h3>Mind Power Artists</h3>
          <small>OG Assistant • Online</small>
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

  function openPanel() {
    panel.classList.add("open");
    input.focus();
    if (!opened) {
      opened = true;
      addMsg(
        "Welcome to Mind Power Artists! 🌿 I'm OG, your MPA AI assistant. How can I help you today?",
        "bot"
      );
    }
  }

  btn.addEventListener("click", () => {
    if (panel.classList.contains("open")) {
      panel.classList.remove("open");
    } else {
      openPanel();
    }
  });

  closeBtn.addEventListener("click", () => panel.classList.remove("open"));

  async function send() {
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;

    addMsg(text, "user");
    const typing = addMsg("OG is typing...", "bot typing");

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
          user_name: "Website Visitor",
          page_url: location.href,
        }),
      });

      const data = await res.json();
      typing.remove();

      if (!res.ok) {
        addMsg("Sorry, something went wrong. Please try again.", "bot");
        return;
      }

      addMsg(data.answer || "Sorry, I couldn't process that.", "bot");
    } catch (e) {
      typing.remove();
      addMsg("Network error. Please check your connection and try again.", "bot");
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
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