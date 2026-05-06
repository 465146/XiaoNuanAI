// ── 聊天逻辑 ──
(function () {
  const messagesEl = document.getElementById("chatMessages");
  const inputEl = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const clearBtn = document.getElementById("clearChat");

  let loading = false;
  let historyLoaded = false;

  function scrollBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addBubble(role, text) {
    const div = document.createElement("div");
    div.className = `chat-bubble ${role}`;
    if (role === "assistant") {
      div.innerHTML = marked.parse(text);
    } else {
      div.textContent = text;
    }
    messagesEl.appendChild(div);
    scrollBottom();
    return div;
  }

  function showWelcome() {
    messagesEl.innerHTML = `
      <div class="chat-welcome">
        <div class="welcome-emoji">🫧</div>
        <h3>嗨，我是小暖 👋</h3>
        <p>一个温暖的 AI 心理陪伴伙伴。<br>无论你想聊什么，我都在这里倾听。</p>
        <p class="welcome-hint">今天感觉怎么样？</p>
      </div>`;
  }

  async function loadHistory() {
    if (historyLoaded) return;
    try {
      const res = await authFetch("/api/chat/history?limit=200");
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (!data.messages || data.messages.length === 0) {
        showWelcome();
        historyLoaded = true;
        return;
      }
      messagesEl.innerHTML = '';
      for (const m of data.messages) {
        addBubble(m.role, m.content);
      }
      historyLoaded = true;
    } catch (err) {
      console.error("Load history error:", err);
      showWelcome();
      historyLoaded = true;
    }
  }

  // 页面加载时自动读取历史
  loadHistory();

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || loading) return;
    inputEl.value = "";
    loading = true;
    sendBtn.disabled = true;

    addBubble("user", text);
    const assistantBubble = addBubble("assistant", "");
    assistantBubble.innerHTML = "<em>思考中...</em>";

    try {
      const response = await authFetch("/api/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let reply = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;
            reply += data;
            assistantBubble.innerHTML = marked.parse(reply);
            scrollBottom();
          }
        }
      }

      if (!reply) assistantBubble.innerHTML = "（小暖正在沉思...请再试一次）";
    } catch (err) {
      assistantBubble.innerHTML = "连接出错了，请稍后重试 😢";
      console.error(err);
    }

    loading = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  clearBtn.addEventListener("click", async () => {
    if (!confirm("确定要清空对话历史吗？")) return;
    await authFetch("/api/chat/clear", { method: "POST" });
    historyLoaded = true;
    showWelcome();
  });
})();
